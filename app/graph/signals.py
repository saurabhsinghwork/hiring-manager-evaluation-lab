"""Deterministic pre-analysis of the three source inputs.

These signals are *hints* handed to the agents next to the raw JSON. They exist so that
facts which regexes extract reliably (company-size tier, sector, title keywords, explicit
reporting lines, employer-name matches) do not depend on a model noticing them. Every
signal carries the source path it came from so agents can cite the underlying field, and
the agents are told to verify hints against the source and to ignore any hint that the
source contradicts.
"""
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Company-size tiers (aligned with the common 1-10 / 11-50 / 51-200 / ... bands)
# --------------------------------------------------------------------------- #
SIZE_TIER_LIMITS = (
    (10, "MICRO"),        # 1-10
    (50, "SMALL"),        # 11-50
    (200, "GROWTH"),      # 51-200
    (1000, "MID_SIZE"),   # 201-1,000
    (10000, "LARGE"),     # 1,001-10,000
)
ENTERPRISE_TIER = "ENTERPRISE"  # 10,001+

_HEADCOUNT_KEYS = {
    "headcount", "employee_count", "employees", "num_employees", "number_of_employees",
    "company_size", "size", "staff_count", "total_employees", "employee_range",
    "workforce", "workforce_size", "employee_size",
}
_MISSING_STRINGS = {"", "not available", "n/a", "na", "none", "unknown", "null", "-", "--", "not provided"}

_NUMBER = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*([kK])?")
_TEXT_SIZE = re.compile(
    r"(\d[\d,]*)\s*(\+|k\+?)?\s*(?:-|–|to)?\s*(\d[\d,]*)?\s*(?:full[- ]time\s+)?"
    r"(?:employees|team members|staff members|staff|associates|colleagues)\b",
    re.IGNORECASE,
)

_SMALL_HINTS = (
    ("pre-seed/seed", r"\bpre-?seed\b|\bseed (?:round|stage|funded)\b"),
    ("series A/B", r"\bseries [ab]\b"),
    ("startup", r"\bstart-?up\b"),
    ("early-stage", r"\bearly[- ]stage\b"),
    ("bootstrapped", r"\bbootstrapped\b"),
    ("founder-led", r"\bfounder[- ]led\b"),
    ("stealth", r"\bstealth\b"),
)
_LARGE_HINTS = (
    ("fortune list", r"\bfortune (?:100|500|1000)\b"),
    ("multinational", r"\bmultinational\b"),
    ("publicly traded", r"\bpublicly traded\b|\bnyse\b|\bnasdaq\b|\bftse\b"),
    ("conglomerate/subsidiary", r"\bconglomerate\b|\bsubsidiary of\b"),
    ("global systemically important", r"\bg-sib\b|\bglobal systemically\b"),
    ("global leader", r"\bglobal (?:bank|insurer|leader)\b"),
)

# --------------------------------------------------------------------------- #
# Sector hints (matter because title conventions differ by sector)
# --------------------------------------------------------------------------- #
_SECTOR_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("FINANCIAL_SERVICES", r"\b(bank|banking|financial services?|financial group|financial holdings|investment bank|asset management|wealth management|"
                           r"capital markets?|brokerage|insurance|insurer|reinsurance|private equity|hedge fund|"
                           r"custody|credit union|mortgage|lending)\b"),
    ("FINTECH", r"\b(fintech|payments?|neobank|digital banking|crypto|blockchain)\b"),
    ("PROFESSIONAL_SERVICES", r"\b(consulting|consultancy|advisory|audit|accounting|law firm|legal services|"
                              r"management consulting|big four)\b"),
    ("GOVERNMENT_PUBLIC_SECTOR", r"\b(government|public sector|federal|municipal|government agency|"
                                 r"defense contractor|civic)\b"),
    ("HEALTHCARE", r"\b(healthcare|health care|hospital|pharma|pharmaceutical|biotech|medical|clinical)\b"),
    ("TECHNOLOGY", r"\b(software|saas|technology|it services|cloud|internet|semiconductor|cybersecurity|"
                   r"information technology|artificial intelligence|ai)\b"),
)
_INDUSTRY_KEYS = {"industry", "sector", "category", "vertical", "business_type"}
_OVERVIEW_KEYS = {"company_overview", "overview", "description", "about", "summary", "company_description"}

# --------------------------------------------------------------------------- #
# Title keyword hints
# --------------------------------------------------------------------------- #
_TITLE_TOKENS: Tuple[Tuple[str, str], ...] = (
    ("RECRUITING_OR_PEOPLE_OPS", r"\b(recruit\w*|talent acquisition|talent partner|talent scout|sourcer|human resources|"
                         r"people operations|people partner|people & culture|people and culture)\b"),
    ("C_SUITE", r"\b(chief|ceo|cto|cio|ciso|cfo|coo|cmo|cpo|cro|cdo|cso)\b"),
    ("FOUNDER_OWNER", r"\b(co-?founder|founder|owner|proprietor|managing partner)\b"),
    ("PRESIDENT", r"(?<!vice\s)(?<!vice-)\bpresident\b"),
    ("MANAGING_DIRECTOR", r"\bmanaging director\b"),
    ("EVP_SVP", r"\b(evp|svp|executive vice[\s-]president|senior vice[\s-]president)\b"),
    ("VICE_PRESIDENT", r"\b(vice[\s-]president|vp)\b"),
    ("ASSISTANT_VP", r"\b(assistant vice[\s-]president|avp)\b"),
    ("DIRECTOR", r"\bdirector\b"),
    ("HEAD_OF", r"\bhead of\b"),
    ("MANAGER", r"\b(manager|mgr)\b"),
    ("NON_PEOPLE_MANAGER_TYPE", r"\b(project|program|programme|product|account|delivery|release|portfolio|"
                                r"customer success|relationship) manager\b"),
    ("TEAM_LEAD", r"\b(team lead|tech lead|technical lead|lead)\b"),
    ("SENIOR_IC_TRACK", r"\b(principal|staff|distinguished|fellow|architect|member of technical staff)\b"),
    ("ADVISORY_OR_INVESTOR", r"\b(advis[eo]r|consultant|investor|venture|board (?:member|director)|fractional|"
                             r"angel|mentor|coach)\b"),
)
_PERSON_TITLE_KEYS = ("current_title", "title", "headline", "job_title", "position", "designation",
                      "current_position", "current_role", "role")
_JD_TITLE_KEYS = ("job_title", "title", "position", "role")
_EXPERIENCE_KEYS = ("experiences", "experience", "positions", "work_history", "employment_history")
_COMPANY_NAME_KEYS = ("company_name", "name", "company", "employer")
_COMPANY_SUFFIX = re.compile(
    r"\b(inc|incorporated|llc|ltd|limited|corp|corporation|co|company|plc|gmbh|sa|ag|group|holdings)\b\.?",
    re.IGNORECASE,
)

_GENERIC_COMPANY_WORDS = {"technology", "technologies", "tech", "software", "company", "the company", "systems",
                          "solutions", "services", "global", "international", "enterprise"}
_JD_AUTHORITY_KEY = re.compile(r"(report|hiring[_ ]?manager|hiring[_ ]?mgr|manager|supervisor|recruiter|owner)", re.IGNORECASE)
_COMPANY_AUTHORITY_KEY = re.compile(
    r"(hiring|policy|policies|rule|authority|approval|approver|org[_ ]?structure|hierarchy|reporting|"
    r"decision|delegat|headcount[_ ]?approval)",
    re.IGNORECASE,
)

# --------------------------------------------------------------------------- #
# Canonical Level Bands and Title Neutralization Heuristics
# --------------------------------------------------------------------------- #
BAND_CANONICAL: Dict[str, int] = {
    "B1_ENTRY_IC": 1,
    "B2_MID_IC": 2,
    "B3_SENIOR_IC": 3,
    "B4_FIRST_LINE_MGR_OR_LEAD": 4,
    "B5_SR_MANAGER": 5,
    "B6_DIRECTOR_HEAD": 6,
    "B7_VP_DIV_HEAD": 7,
    "B8_C_LEVEL_FOUNDER": 8,
}
BAND_NAMES: Dict[int, str] = {v: k for k, v in BAND_CANONICAL.items()}

# Corporate rank regexes for Financial Services
_FS_MD = re.compile(r"\b(managing director|md)\b", re.IGNORECASE)
_FS_ED = re.compile(r"\b(executive director|ed)\b", re.IGNORECASE)
_FS_SVP = re.compile(r"\b(senior vice[\s-]president|svp|evp)\b", re.IGNORECASE)
_FS_AVP = re.compile(r"\b(assistant vice[\s-]president|avp)\b", re.IGNORECASE)
_FS_VP = re.compile(r"(?<!assistant\s)(?<!senior\s)(?<!executive\s)\b(vice[\s-]president|vp)\b", re.IGNORECASE)
_FS_ASSOC = re.compile(r"\bassociate\b", re.IGNORECASE)
_FS_ANALYST = re.compile(r"\banalyst\b", re.IGNORECASE)

# Standard hierarchy regexes
_C_LEVEL_FOUNDER = re.compile(
    r"\b(chief\s+(?:executive|technology|information|security|financial|operating|product|revenue|data|compliance|legal)\s+officer|"
    r"ceo|cto|cio|ciso|cfo|coo|cpo|cro|cdo|founder|co-founder|proprietor|managing partner)\b",
    re.IGNORECASE,
)
_VP_GENERAL = re.compile(r"\b(vice[\s-]president|vp|svp|evp)\b", re.IGNORECASE)
_DIRECTOR_GENERAL = re.compile(r"\b(senior\s+director|sr\.?\s+director|director|head of)\b", re.IGNORECASE)
_SR_MANAGER = re.compile(r"\b(senior manager|sr\.?\s+manager|group manager|associate director)\b", re.IGNORECASE)
_MANAGER_LEAD = re.compile(r"\b(engineering manager|software engineering manager|devops manager|qa manager|technical lead|tech lead|team lead|manager|mgr|supervisor)\b", re.IGNORECASE)
_NON_PEOPLE_MANAGER = re.compile(r"\b(project|program|programme|product|account|delivery|release|portfolio|customer success|relationship)\s+manager\b", re.IGNORECASE)
_SENIOR_IC_TRACK = re.compile(r"\b(principal|staff|distinguished|fellow|chief\s+architect|lead\s+architect|architect|senior|sr\.?)\b", re.IGNORECASE)
_MID_IC_TRACK = re.compile(r"\b(engineer|developer|specialist|consultant|programmer|analyst|designer)\b", re.IGNORECASE)
_ENTRY_IC_TRACK = re.compile(r"\b(junior|jr\.?|intern|trainee|entry|associate)\b", re.IGNORECASE)

_HEADCOUNT_EXTRACT = re.compile(r"(\d+)\s*(?:\+\s*)?(?:direct\s+reports|reports|engineers|developers|people|staff|members|pods)", re.IGNORECASE)
_TEAM_SIZE_EXTRACT = re.compile(r"(?:team\s+of|managed|led|supervised|directing|leading)\s*(\d+)", re.IGNORECASE)
_MGMT_ACTION_VERBS = re.compile(
    r"\b(lead(?:ing)?(?:\s+[a-z]+){0,3}\s+(?:organizations?|teams?|departments?|divisions?|pods)|"
    r"manag(?:ing|ed)(?:\s+[a-z]+){0,3}\s+(?:organizations?|teams?|departments?|divisions?|pods)|"
    r"direct reports|hiring|hired|budget|headcount|performance reviews?|supervising|people manager|"
    r"people management|reporting to me)\b",
    re.IGNORECASE,
)
_IC_ACTION_VERBS = re.compile(r"\b(architected|developed|coded|authored|engineered|implemented|designed\s+(?:ui|components|library|system|schema)|hands[- ]on|individual contributor|ic)\b", re.IGNORECASE)



# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in _MISSING_STRINGS
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _walk(node: Any, path: str = "") -> Iterator[Tuple[str, str, Any]]:
    """Yields (path, key, value) for every node; list items get an empty key."""
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else str(key)
            yield child, str(key), value
            yield from _walk(value, child)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            child = f"{path}[{index}]"
            yield child, "", value
            yield from _walk(value, child)


def _norm_key(key: str) -> str:
    return re.sub(r"[\s\-]+", "_", key.strip().lower())


def size_tier_for(count: int) -> str:
    """Maps an employee count to a size tier."""
    for limit, name in SIZE_TIER_LIMITS:
        if count <= limit:
            return name
    return ENTERPRISE_TIER


def _numbers(text: str) -> List[int]:
    values: List[int] = []
    for match in _NUMBER.finditer(text):
        number = float(match.group(1).replace(",", ""))
        if match.group(2):
            number *= 1000
        values.append(int(number))
    return values


def _parse_size_value(value: Any) -> Optional[Tuple[int, Optional[int], bool]]:
    """Returns (low, high, open_ended) or None. high is None for a point/open-ended value."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return (int(value), None, False) if value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text.lower() in _MISSING_STRINGS:
            return None
        nums = _numbers(text)
        if not nums:
            return None
        open_ended = bool(re.search(r"\+|\bover\b|\bmore than\b|\bat least\b|\babove\b", text, re.IGNORECASE))
        if len(nums) >= 2 and re.search(r"\d\s*(?:-|–|to)\s*\d", text, re.IGNORECASE):
            low, high = sorted(nums[:2])
            return (low, high, False)
        return (nums[0], None, open_ended) if nums[0] > 0 else None
    return None


def _tier_description(low: int, high: Optional[int]) -> str:
    low_tier = size_tier_for(low)
    if high is None:
        return low_tier
    high_tier = size_tier_for(high)
    return low_tier if low_tier == high_tier else f"{low_tier}_TO_{high_tier}"


def _tier_note(low: int, high: Optional[int], open_ended: bool) -> str:
    if open_ended:
        return "Open-ended value: the true size is at least this large."
    if "_TO_" in _tier_description(low, high):
        return "Range straddles tiers: apply the conservative reading and state both."
    return "Structured headcount field."


def _strings(node: Any, path: str = "") -> Iterator[Tuple[str, str]]:
    for child_path, _key, value in _walk(node, path):
        if isinstance(value, str) and value.strip():
            yield child_path, value


def derive_company_size(company_context: Dict[str, Any]) -> Dict[str, Any]:
    """Derives the company-size tier from structured fields first, free text second."""
    result: Dict[str, Any] = {
        "size_tier": "UNKNOWN",
        "basis": "NONE",
        "source_path": None,
        "raw_value": None,
        "employee_count_low": None,
        "employee_count_high": None,
        "open_ended_lower_bound": False,
        "tier_note": "No usable headcount found. Do not assume a size; reason under both a smaller and a larger "
                     "reading, state which verdict changes, and cap confidence accordingly.",
    }
    for path, key, value in _walk(company_context, "company_context"):
        if _norm_key(key) in _HEADCOUNT_KEYS and not isinstance(value, (dict, list)):
            parsed = _parse_size_value(value)
            if parsed:
                low, high, open_ended = parsed
                result.update(
                    size_tier=_tier_description(low, high),
                    basis="STRUCTURED_FIELD",
                    source_path=path,
                    raw_value=value,
                    employee_count_low=low,
                    employee_count_high=high,
                    open_ended_lower_bound=open_ended,
                    tier_note=_tier_note(low, high, open_ended),
                )
                return result

    for path, text in _strings(company_context, "company_context"):
        match = _TEXT_SIZE.search(text)
        if match:
            low = int(float(match.group(1).replace(",", "")) * (1000 if (match.group(2) or "").lower().startswith("k") else 1))
            high = int(match.group(3).replace(",", "")) if match.group(3) else None
            if high is not None and high < low:
                low, high = high, low
            result.update(
                size_tier=_tier_description(low, high),
                basis="TEXT_MENTION",
                source_path=path,
                raw_value=match.group(0).strip(),
                employee_count_low=low,
                employee_count_high=high,
                open_ended_lower_bound=bool(match.group(2) and "+" in match.group(2)),
                tier_note="Derived from free text: lower reliability than a structured field.",
            )
            return result
    return result


def _size_hints(company_context: Dict[str, Any]) -> Dict[str, List[str]]:
    text = " \n ".join(value for _, value in _strings(company_context)).lower()
    small = [label for label, pattern in _SMALL_HINTS if re.search(pattern, text)]
    large = [label for label, pattern in _LARGE_HINTS if re.search(pattern, text)]
    return {"small_company_cues": small, "large_company_cues": large}


def derive_sector(company_context: Dict[str, Any]) -> Dict[str, Any]:
    """Finds the sector hint from industry-like fields (preferred) or the overview text."""
    primary: List[Tuple[str, str]] = []
    secondary: List[Tuple[str, str]] = []
    industry_fields: List[Tuple[str, str]] = []
    for path, key, value in _walk(company_context, "company_context"):
        if not isinstance(value, str) or _is_missing(value):
            continue
        nkey = _norm_key(key)
        if nkey in _INDUSTRY_KEYS:
            industry_fields.append((path, value))
            primary.append((path, value))
        elif nkey == "company_name":
            primary.append((path, value))
        elif nkey in _OVERVIEW_KEYS:
            secondary.append((path, value))
    for sector, pattern in _SECTOR_PATTERNS:
        for path, value in primary:
            if re.search(pattern, value, re.IGNORECASE):
                return {"sector_hint": sector, "basis": "INDUSTRY_FIELD", "source_path": path}
    if industry_fields:
        # An explicit industry exists but maps to no sector with special title conventions.
        # Do not let a stray word in the free-text overview override it.
        path, value = industry_fields[0]
        return {"sector_hint": "OTHER", "basis": "INDUSTRY_FIELD", "source_path": path, "industry_value": value}
    for sector, pattern in _SECTOR_PATTERNS:
        for path, value in secondary:
            if re.search(pattern, value, re.IGNORECASE):
                return {"sector_hint": sector, "basis": "OVERVIEW_TEXT", "source_path": path}
    return {"sector_hint": "UNKNOWN", "basis": "NONE", "source_path": None}


def clean_title(title: str) -> str:
    if not title:
        return ""
    return re.split(r"\s*[@\|•]\s*", title)[0].strip()


def neutralize_title(title: str, sector: str = "UNKNOWN") -> Dict[str, Any]:
    cleaned = clean_title(title)
    is_fs = sector == "FINANCIAL_SERVICES"

    corporate_rank = None
    is_corp_rank = False
    is_non_people_mgr = bool(_NON_PEOPLE_MANAGER.search(cleaned))
    band_name = "B2_MID_IC"
    band_num = 2
    notes = ""

    # Financial services title conventions (BNY, Citi, JPMorgan, etc.)
    if is_fs:
        if _FS_MD.search(cleaned):
            corporate_rank = "Managing Director"
            is_corp_rank = True
            band_name = "B6_DIRECTOR_HEAD"
            band_num = 6
            notes = "In Financial Services, Managing Director is a senior executive / divisional officer rank."
        elif _FS_ED.search(cleaned):
            corporate_rank = "Executive Director"
            is_corp_rank = True
            band_name = "B5_SR_MANAGER"
            band_num = 5
            notes = "In Financial Services, Executive Director sits between VP and MD (Director/Senior Manager equivalent)."
        elif _FS_SVP.search(cleaned):
            corporate_rank = "Senior Vice President"
            is_corp_rank = True
            band_name = "B4_FIRST_LINE_MGR_OR_LEAD"
            band_num = 4
            notes = "In Financial Services, SVP is an upper-mid corporate rank above VP."
        elif _FS_AVP.search(cleaned):
            corporate_rank = "Assistant Vice President"
            is_corp_rank = True
            band_name = "B2_MID_IC"
            band_num = 2
            notes = "In Financial Services, AVP is an intermediate professional grade (mid-level IC)."
        elif _FS_VP.search(cleaned):
            corporate_rank = "Vice President"
            is_corp_rank = True
            has_mgr = bool(_MANAGER_LEAD.search(cleaned) and not is_non_people_mgr)
            has_head = bool(re.search(r"\bhead of\b", cleaned, re.IGNORECASE))
            if has_mgr or has_head:
                band_name = "B4_FIRST_LINE_MGR_OR_LEAD"
                band_num = 4
                notes = "In Financial Services, Vice President is a corporate rank; explicit manager/head qualification indicates team lead / line manager (B4)."
            else:
                band_name = "B3_SENIOR_IC"
                band_num = 3
                notes = "In Financial Services, 'Vice President' is a mid-career corporate compensation rank held by senior ICs, architects, and tech leads; it does NOT denote executive hiring authority."
        elif _C_LEVEL_FOUNDER.search(cleaned):
            band_name = "B8_C_LEVEL_FOUNDER"
            band_num = 8
            notes = "Executive leadership / Founder."
        elif _DIRECTOR_GENERAL.search(cleaned):
            corporate_rank = "Director"
            is_corp_rank = True
            band_name = "B5_SR_MANAGER"
            band_num = 5
            notes = "Director rank in financial services."
        elif _SR_MANAGER.search(cleaned):
            band_name = "B5_SR_MANAGER"
            band_num = 5
        elif _MANAGER_LEAD.search(cleaned) and not is_non_people_mgr:
            band_name = "B4_FIRST_LINE_MGR_OR_LEAD"
            band_num = 4
        elif _SENIOR_IC_TRACK.search(cleaned):
            band_name = "B3_SENIOR_IC"
            band_num = 3
        elif _ENTRY_IC_TRACK.search(cleaned):
            band_name = "B1_ENTRY_IC"
            band_num = 1
        else:
            band_name = "B2_MID_IC"
            band_num = 2
    else:
        # General / Tech / Startup conventions
        if _C_LEVEL_FOUNDER.search(cleaned):
            band_name = "B8_C_LEVEL_FOUNDER"
            band_num = 8
            notes = "Top executive / C-suite / Founder."
        elif _VP_GENERAL.search(cleaned):
            band_name = "B7_VP_DIV_HEAD"
            band_num = 7
            notes = "VP level executive (standard tech/commercial hierarchy)."
        elif _DIRECTOR_GENERAL.search(cleaned):
            band_name = "B6_DIRECTOR_HEAD"
            band_num = 6
            notes = "Director / Head of function."
        elif _SR_MANAGER.search(cleaned):
            band_name = "B5_SR_MANAGER"
            band_num = 5
            notes = "Senior manager / group manager."
        elif _MANAGER_LEAD.search(cleaned):
            if is_non_people_mgr:
                band_name = "B3_SENIOR_IC"
                band_num = 3
                notes = "Project/Product/Program manager: typically individual contributor / non-people-manager track."
            else:
                band_name = "B4_FIRST_LINE_MGR_OR_LEAD"
                band_num = 4
                notes = "First-line people manager or tech lead with team oversight."
        elif _SENIOR_IC_TRACK.search(cleaned):
            band_name = "B3_SENIOR_IC"
            band_num = 3
            notes = "Senior / Staff / Principal / Architect IC track."
        elif _ENTRY_IC_TRACK.search(cleaned):
            band_name = "B1_ENTRY_IC"
            band_num = 1
            notes = "Entry / Junior IC track."
        elif _MID_IC_TRACK.search(cleaned):
            band_name = "B2_MID_IC"
            band_num = 2
            notes = "Mid-level IC engineer / specialist."
        else:
            band_name = "B2_MID_IC"
            band_num = 2
            notes = "Default mid IC band."

    return {
        "raw_title": title,
        "cleaned_title": cleaned,
        "canonical_band": band_name,
        "band_number": band_num,
        "corporate_rank": corporate_rank,
        "is_corporate_rank_grade": is_corp_rank,
        "is_non_people_manager_track": is_non_people_mgr,
        "notes": notes,
    }


def neutralize_job_level(job_description: Dict[str, Any], sector: str = "UNKNOWN") -> Dict[str, Any]:
    raw_level = str(job_description.get("level") or "").strip()
    raw_title = str(job_description.get("job_title") or "").strip()

    band_name = "B2_MID_IC"
    band_num = 2
    basis = "DEFAULT"

    if re.search(r"\b(director|head\s+of)\b", raw_title, re.I):
        band_name = "B6_DIRECTOR_HEAD"
        band_num = 6
        basis = "TITLE_DIRECTOR"
    elif re.search(r"\b(engineering\s+manager|manager)\b", raw_title, re.I) and not _NON_PEOPLE_MANAGER.search(raw_title):
        band_name = "B4_FIRST_LINE_MGR_OR_LEAD"
        band_num = 4
        basis = "TITLE_MANAGER"
    elif re.search(r"\b(senior|sr\.?|staff|principal|lead|architect)\b", raw_title, re.I) or re.search(r"\b(senior|sr\.?|staff|principal|architect)\b", raw_level, re.I):
        band_name = "B3_SENIOR_IC"
        band_num = 3
        basis = "TITLE_OR_LEVEL_SENIOR"
    elif re.search(r"\b(junior|jr\.?|entry|intern|associate)\b", raw_title, re.I) or re.search(r"\b(junior|entry|intern)\b", raw_level, re.I):
        band_name = "B1_ENTRY_IC"
        band_num = 1
        basis = "TITLE_OR_LEVEL_JUNIOR"
    elif re.search(r"\b(mid|intermediate|experienced)\b", raw_level, re.I):
        band_name = "B2_MID_IC"
        band_num = 2
        basis = "LEVEL_MID"
    else:
        band_name = "B2_MID_IC"
        band_num = 2
        basis = "STANDARD_IC_ROLE"

    return {
        "job_title": raw_title,
        "stated_level": raw_level if raw_level else "Not Available",
        "canonical_band": band_name,
        "band_number": band_num,
        "basis": basis,
    }


def derive_title_neutralization(
    candidate_profile: Dict[str, Any],
    job_description: Dict[str, Any],
    sector: str = "UNKNOWN",
) -> Dict[str, Any]:
    primary_title = candidate_profile.get("current_title", "")
    experiences = candidate_profile.get("experiences")
    if isinstance(experiences, list) and len(experiences) > 0 and isinstance(experiences[0], dict):
        exp_title = experiences[0].get("title")
        if exp_title and not _is_missing(exp_title):
            primary_title = exp_title

    cand_canonical = neutralize_title(str(primary_title or ""), sector)
    job_canonical = neutralize_job_level(job_description, sector)

    return {
        "candidate_canonical": cand_canonical,
        "job_canonical": job_canonical,
        "notes": (
            "Titles are mapped to standardized organizational bands (B1 to B8). "
            "In Financial Services, corporate ranks (e.g. Vice President) are normalized to functional IC/manager bands."
        ),
    }


def extract_management_evidence(candidate_profile: Dict[str, Any]) -> Dict[str, Any]:
    experiences = candidate_profile.get("experiences", [])
    summary = str(candidate_profile.get("summary") or "")

    mgmt_text = " ".join([
        summary,
        str(candidate_profile.get("current_title") or ""),
    ])
    if isinstance(experiences, list):
        for exp in experiences[:5]:
            if isinstance(exp, dict):
                mgmt_text += " " + str(exp.get("description") or "") + " " + str(exp.get("title") or "")

    counts: List[int] = []
    for m in _HEADCOUNT_EXTRACT.finditer(mgmt_text):
        try:
            counts.append(int(m.group(1)))
        except ValueError:
            pass
    for m in _TEAM_SIZE_EXTRACT.finditer(mgmt_text):
        try:
            counts.append(int(m.group(1)))
        except ValueError:
            pass

    mgmt_cues = list(set(c.lower() for c in _MGMT_ACTION_VERBS.findall(mgmt_text)))
    ic_cues = list(set(c.lower() for c in _IC_ACTION_VERBS.findall(mgmt_text)))

    max_headcount = max(counts) if counts else None

    if max_headcount is not None and max_headcount > 0:
        status = "PEOPLE_MANAGER"
        notes = f"Evidenced direct oversight of {max_headcount}+ team members."
    elif len(mgmt_cues) >= 1 and len(ic_cues) == 0:
        status = "PEOPLE_MANAGER"
        notes = f"People management vocabulary evidenced ({', '.join(mgmt_cues)}) without individual contributor tasks."
    elif len(mgmt_cues) >= 1 and len(ic_cues) >= 1:
        status = "PLAYER_COACH"
        notes = "Evidences both hands-on technical execution and team leading / management activities."
    elif len(ic_cues) >= 1 and len(mgmt_cues) == 0 and not counts:
        status = "INDIVIDUAL_CONTRIBUTOR"
        notes = f"Description consists of hands-on technical execution ({', '.join(ic_cues)}) with no evidenced reports."
    else:
        status = "INDIVIDUAL_CONTRIBUTOR" if len(ic_cues) > 0 else "UNKNOWN"
        notes = "No explicit people-management or direct reports evidenced in profile text."

    return {
        "management_status_hint": status,
        "evidenced_team_size": max_headcount,
        "management_cues": mgmt_cues,
        "individual_contributor_cues": ic_cues,
        "notes": notes,
    }


def calculate_relative_reach(
    person_band: int,
    job_band: int,
    size_tier: str,
    sector: str = "UNKNOWN",
    is_owning_function_head: bool = False,
    management_status: str = "UNKNOWN",
    is_non_people_manager_track: bool = False,
) -> Dict[str, Any]:
    delta = person_band - job_band

    if delta < 0:
        return {
            "delta": delta,
            "classification": "SUBORDINATE",
            "is_structurally_plausible_hiring_manager": False,
            "hiring_manager_recommendation": "AGAINST",
            "notes": f"Candidate band (B{person_band}) sits below the job opening band (B{job_band}); Delta = {delta}. Subordinates do not hire superiors.",
        }

    if delta == 0:
        return {
            "delta": 0,
            "classification": "PEER_OR_KEY_TECHNICAL_INFLUENCER",
            "is_structurally_plausible_hiring_manager": False,
            "hiring_manager_recommendation": "AGAINST_LINE_HM_PLAUSIBLE_INTERVIEWER",
            "notes": f"Candidate sits at the exact same organizational band (B{person_band}) as the opening (Delta = 0). Plausible technical evaluator, interviewer, or peer influencer, but NOT the primary line hiring manager who owns the requisition.",
        }

    if is_non_people_manager_track and not is_owning_function_head:
        return {
            "delta": delta,
            "classification": "NON_PEOPLE_MANAGER_TRACK",
            "is_structurally_plausible_hiring_manager": False,
            "hiring_manager_recommendation": "AGAINST_LINE_HM_PLAUSIBLE_INFLUENCER",
            "notes": "Candidate title represents a project, program, or product manager track. These roles coordinate initiatives but do not have line hiring authority over technical roles.",
        }

    # delta > 0
    if size_tier in ("MICRO", "SMALL", "GROWTH") and (is_owning_function_head or person_band == 8 or delta <= 5):
        return {
            "delta": delta,
            "classification": "STARTUP_OR_GROWTH_FUNCTION_HEAD",
            "is_structurally_plausible_hiring_manager": True,
            "hiring_manager_recommendation": "FOR",
            "notes": f"In {size_tier} organizations (flat structure), founders and owning function heads (CTO/VP) directly hire and approve requisitions across the department (Delta = +{delta}).",
        }

    if size_tier in ("LARGE", "ENTERPRISE"):
        if delta in (1, 2):
            if management_status == "INDIVIDUAL_CONTRIBUTOR":
                return {
                    "delta": delta,
                    "classification": "TECHNICAL_LEAD_OR_ARCHITECT_WITHOUT_REPORTS",
                    "is_structurally_plausible_hiring_manager": False,
                    "hiring_manager_recommendation": "AGAINST_LINE_HM_PLAUSIBLE_INFLUENCER",
                    "notes": f"Band is Delta = +{delta}, but evidence indicates an individual contributor/architect without direct reports. Has technical influence but not requisition hiring authority.",
                }
            return {
                "delta": delta,
                "classification": "STRUCTURALLY_PLAUSIBLE_LINE_MANAGER",
                "is_structurally_plausible_hiring_manager": True,
                "hiring_manager_recommendation": "FOR",
                "notes": f"In {size_tier} organizations, first-line or skip-level managers (Delta = +{delta}) directly own and hire for team openings.",
            }
        else:  # delta >= 3
            return {
                "delta": delta,
                "classification": "TOO_DISTANT_EXECUTIVE",
                "is_structurally_plausible_hiring_manager": False,
                "hiring_manager_recommendation": "AGAINST",
                "notes": f"In {size_tier} organizations (1,001+ employees), executive layers (Delta = +{delta}) sit too many management layers above an IC opening to serve as the direct hiring manager.",
            }

    if size_tier == "MID_SIZE":
        if delta in (1, 2):
            return {
                "delta": delta,
                "classification": "STRUCTURALLY_PLAUSIBLE_LINE_MANAGER",
                "is_structurally_plausible_hiring_manager": True,
                "hiring_manager_recommendation": "FOR",
                "notes": f"In MID_SIZE organizations, line managers or department heads (Delta = +{delta}) own team requisitions.",
            }
        elif delta == 3 and is_owning_function_head:
            return {
                "delta": delta,
                "classification": "STRUCTURALLY_PLAUSIBLE_LINE_MANAGER",
                "is_structurally_plausible_hiring_manager": True,
                "hiring_manager_recommendation": "FOR",
                "notes": f"In MID_SIZE organizations, the department head (Delta = +{delta}) is within plausible reach.",
            }
        else:
            return {
                "delta": delta,
                "classification": "TOO_DISTANT_EXECUTIVE",
                "is_structurally_plausible_hiring_manager": False,
                "hiring_manager_recommendation": "AGAINST",
                "notes": f"In MID_SIZE organizations, executives at Delta = +{delta} sit above the requisition owner.",
            }

    # Default / Unknown
    if delta in (1, 2):
        return {
            "delta": delta,
            "classification": "STRUCTURALLY_PLAUSIBLE_LINE_MANAGER",
            "is_structurally_plausible_hiring_manager": True,
            "hiring_manager_recommendation": "FOR",
            "notes": f"Delta = +{delta} is structurally plausible for a line manager.",
        }
    return {
        "delta": delta,
        "classification": "SIZE_DEPENDENT_REACH",
        "is_structurally_plausible_hiring_manager": (delta <= 3),
        "hiring_manager_recommendation": "UNRESOLVED_SIZE_DEPENDENCY",
        "notes": f"Plausibility at Delta = +{delta} depends on company size (plausible at small companies, too distant at enterprise).",
    }


def _title_tokens(text: str) -> List[str]:
    return [name for name, pattern in _TITLE_TOKENS if re.search(pattern, text, re.IGNORECASE)]


def _person_titles(candidate_profile: Dict[str, Any], sector: str = "UNKNOWN") -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    for key in _PERSON_TITLE_KEYS:
        value = candidate_profile.get(key)
        if isinstance(value, str) and not _is_missing(value):
            neut = neutralize_title(value, sector)
            found.append({
                "path": f"candidate_profile.{key}",
                "value": value,
                "keyword_hints": _title_tokens(value),
                "neutralized_band": neut["canonical_band"],
                "band_number": neut["band_number"],
                "is_corporate_rank_grade": neut["is_corporate_rank_grade"],
            })
    for key in _EXPERIENCE_KEYS:
        entries = candidate_profile.get(key)
        if isinstance(entries, list):
            for index, entry in enumerate(entries[:3]):
                if isinstance(entry, dict):
                    title = entry.get("title") or entry.get("role") or entry.get("position")
                    if isinstance(title, str) and not _is_missing(title):
                        neut = neutralize_title(title, sector)
                        found.append({
                            "path": f"candidate_profile.{key}[{index}].title",
                            "value": title,
                            "company": entry.get("company"),
                            "keyword_hints": _title_tokens(title),
                            "neutralized_band": neut["canonical_band"],
                            "band_number": neut["band_number"],
                            "is_corporate_rank_grade": neut["is_corporate_rank_grade"],
                        })
            break
    return found


def _job_titles(job_description: Dict[str, Any], sector: str = "UNKNOWN") -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    for key in _JD_TITLE_KEYS:
        value = job_description.get(key)
        if isinstance(value, str) and not _is_missing(value):
            neut = neutralize_job_level(job_description, sector)
            found.append({
                "path": f"job_description.{key}",
                "value": value,
                "keyword_hints": _title_tokens(value),
                "neutralized_band": neut["canonical_band"],
                "band_number": neut["band_number"],
            })
    return found


def _normalize_company(name: str) -> str:
    cleaned = _COMPANY_SUFFIX.sub(" ", name.lower())
    return re.sub(r"[^a-z0-9]+", " ", cleaned).strip()


def _employer_match(candidate_profile: Dict[str, Any], company_context: Dict[str, Any]) -> Dict[str, Any]:
    names = [v for k in _COMPANY_NAME_KEYS
             for v in [company_context.get(k)] if isinstance(v, str) and not _is_missing(v)]
    if not names:
        return {"company_name": None, "found_in_profile_at": [], "note": "No company name in company_context."}
    target = _normalize_company(names[0])
    if len(target) < 3 or target in _GENERIC_COMPANY_WORDS:
        return {"company_name": names[0], "found_in_profile_at": [], "note": "Company name too generic to match."}
    pattern = re.compile(r"(?<![a-z0-9])" + re.escape(target) + r"(?![a-z0-9])")
    hits = [path for path, text in _strings(candidate_profile, "candidate_profile")
            if pattern.search(re.sub(r"[^a-z0-9]+", " ", _COMPANY_SUFFIX.sub(" ", text.lower())))]
    note = ("Company name appears in the profile; still confirm the role there is CURRENT."
            if hits else
            "Company name NOT found anywhere in the profile: treat as a possible employer mismatch unless the "
            "context name is generic or a brand/legal-name variant of the profile's employer.")
    return {"company_name": names[0], "found_in_profile_at": hits[:8], "note": note}


def _clip(value: Any, limit: int = 500) -> Any:
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "…"
    return value


def _authoritative_statements(
    job_description: Dict[str, Any], company_context: Dict[str, Any]
) -> Dict[str, List[Dict[str, Any]]]:
    jd_items: List[Dict[str, Any]] = []
    for path, key, value in _walk(job_description, "job_description"):
        if key and _JD_AUTHORITY_KEY.search(key) and not _is_missing(value):
            if isinstance(value, (dict, list)):
                continue  # children are visited separately
            jd_items.append({"path": path, "value": _clip(value)})
    co_items: List[Dict[str, Any]] = []
    for path, key, value in _walk(company_context, "company_context"):
        if key and _COMPANY_AUTHORITY_KEY.search(key) and not _is_missing(value):
            if isinstance(value, (dict, list)):
                continue
            co_items.append({"path": path, "value": _clip(value)})
    return {"job_description_fields": jd_items[:12], "company_context_fields": co_items[:20]}


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def derive_context_signals(
    candidate_profile: Dict[str, Any],
    job_description: Dict[str, Any],
    company_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Builds the derived-signals block. Never raises: any failure yields an empty-safe block."""
    try:
        size = derive_company_size(company_context)
        size["cues"] = _size_hints(company_context)
        sector_info = derive_sector(company_context)
        sector_hint = sector_info.get("sector_hint", "UNKNOWN")
        size_tier = size.get("size_tier", "UNKNOWN")

        title_neutralization = derive_title_neutralization(candidate_profile, job_description, sector_hint)
        management_evidence = extract_management_evidence(candidate_profile)

        person_band_num = title_neutralization["candidate_canonical"]["band_number"]
        job_band_num = title_neutralization["job_canonical"]["band_number"]
        is_owning_function_head = (
            person_band_num == 8
            or bool(re.search(r"\b(cto|chief\s+technology\s+officer|head\s+of\s+engineering|vp\s+of\s+engineering)\b", title_neutralization["candidate_canonical"]["cleaned_title"], re.I))
        )
        is_non_people_mgr = title_neutralization["candidate_canonical"]["is_non_people_manager_track"]
        mgmt_status = management_evidence["management_status_hint"]

        relative_reach = calculate_relative_reach(
            person_band=person_band_num,
            job_band=job_band_num,
            size_tier=size_tier,
            sector=sector_hint,
            is_owning_function_head=is_owning_function_head,
            management_status=mgmt_status,
            is_non_people_manager_track=is_non_people_mgr,
        )

        return {
            "company_size": size,
            "sector": sector_info,
            "employer_match": _employer_match(candidate_profile, company_context),
            "person_titles": _person_titles(candidate_profile, sector_hint),
            "job_titles": _job_titles(job_description, sector_hint),
            "title_neutralization": title_neutralization,
            "management_evidence": management_evidence,
            "relative_reach": relative_reach,
            "explicit_authority_statements": _authoritative_statements(job_description, company_context),
            "caveat": "Automated hints. Verify against the source JSON; if the source contradicts a hint, the "
                      "source wins. keyword_hints are lexical only and never establish authority by themselves.",
        }
    except Exception as exc:  # pragma: no cover - defensive: hints must never break the workflow
        return {"error": f"signal derivation failed: {type(exc).__name__}", "caveat": "Ignore this block."}

