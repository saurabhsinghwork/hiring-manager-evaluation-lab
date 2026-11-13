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


def _title_tokens(text: str) -> List[str]:
    return [name for name, pattern in _TITLE_TOKENS if re.search(pattern, text, re.IGNORECASE)]


def _person_titles(candidate_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    for key in _PERSON_TITLE_KEYS:
        value = candidate_profile.get(key)
        if isinstance(value, str) and not _is_missing(value):
            found.append({"path": f"candidate_profile.{key}", "value": value, "keyword_hints": _title_tokens(value)})
    for key in _EXPERIENCE_KEYS:
        entries = candidate_profile.get(key)
        if isinstance(entries, list):
            for index, entry in enumerate(entries[:3]):
                if isinstance(entry, dict):
                    title = entry.get("title") or entry.get("role") or entry.get("position")
                    if isinstance(title, str) and not _is_missing(title):
                        found.append({
                            "path": f"candidate_profile.{key}[{index}].title",
                            "value": title,
                            "company": entry.get("company"),
                            "keyword_hints": _title_tokens(title),
                        })
            break
    return found


def _job_titles(job_description: Dict[str, Any]) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    for key in _JD_TITLE_KEYS:
        value = job_description.get(key)
        if isinstance(value, str) and not _is_missing(value):
            found.append({"path": f"job_description.{key}", "value": value, "keyword_hints": _title_tokens(value)})
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
        return {
            "company_size": size,
            "sector": derive_sector(company_context),
            "employer_match": _employer_match(candidate_profile, company_context),
            "person_titles": _person_titles(candidate_profile),
            "job_titles": _job_titles(job_description),
            "explicit_authority_statements": _authoritative_statements(job_description, company_context),
            "caveat": "Automated hints. Verify against the source JSON; if the source contradicts a hint, the "
                      "source wins. keyword_hints are lexical only and never establish authority by themselves.",
        }
    except Exception as exc:  # pragma: no cover - defensive: hints must never break the workflow
        return {"error": f"signal derivation failed: {type(exc).__name__}", "caveat": "Ignore this block."}
