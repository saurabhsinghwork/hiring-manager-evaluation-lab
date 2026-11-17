"""Tests for title neutralization, relative reach calculus, and management evidence extraction."""
import json
from pathlib import Path
import pytest

from app.graph.signals import (
    derive_context_signals,
    derive_title_neutralization,
    neutralize_title,
    neutralize_job_level,
    extract_management_evidence,
    calculate_relative_reach,
)

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"
REAL_20_PATH = SAMPLES / "new_20_real_datasets.json"


# --------------------------------------------------------------------------- #
# Title Neutralization - Financial Services Title Mirage vs General Tech
# --------------------------------------------------------------------------- #
def test_financial_services_vp_mirage_neutralization():
    """In financial services (BNY, Citi, JPMC), Vice President is corporate rank for senior ICs."""
    res_bny_vp = neutralize_title("Vice President, Software Engineering: Treasury and Payment Services", sector="FINANCIAL_SERVICES")
    assert res_bny_vp["canonical_band"] == "B3_SENIOR_IC"
    assert res_bny_vp["band_number"] == 3
    assert res_bny_vp["corporate_rank"] == "Vice President"
    assert res_bny_vp["is_corporate_rank_grade"] is True

    res_cloud_vp = neutralize_title("Vice President of Cloud Infrastructure", sector="FINANCIAL_SERVICES")
    assert res_cloud_vp["canonical_band"] == "B3_SENIOR_IC"
    assert res_cloud_vp["band_number"] == 3
    assert res_cloud_vp["is_corporate_rank_grade"] is True


def test_financial_services_executive_ranks():
    """Managing Director and AVP in banking hierarchies."""
    md = neutralize_title("Managing Director, Site Reliability Engineering @ BNY", sector="FINANCIAL_SERVICES")
    assert md["canonical_band"] == "B6_DIRECTOR_HEAD"
    assert md["band_number"] == 6
    assert md["corporate_rank"] == "Managing Director"
    assert md["is_corporate_rank_grade"] is True

    avp = neutralize_title("Assistant Vice President, Platform Engineering", sector="FINANCIAL_SERVICES")
    assert avp["canonical_band"] == "B2_MID_IC"
    assert avp["band_number"] == 2
    assert avp["corporate_rank"] == "Assistant Vice President"


def test_standard_and_tech_titles():
    """In non-financial services, standard hierarchy applies."""
    mgr = neutralize_title("Engineering Manager and Technical Lead | Design Systems", sector="TECHNOLOGY")
    assert mgr["canonical_band"] == "B4_FIRST_LINE_MGR_OR_LEAD"
    assert mgr["band_number"] == 4

    cto = neutralize_title("Co-Founder & CTO @ Hone Health", sector="TECHNOLOGY")
    assert cto["canonical_band"] == "B8_C_LEVEL_FOUNDER"
    assert cto["band_number"] == 8

    chief_arch = neutralize_title("Chief Architect", sector="TECHNOLOGY")
    assert chief_arch["canonical_band"] == "B3_SENIOR_IC"
    assert chief_arch["band_number"] == 3

    prog_mgr = neutralize_title("Information Technology Program Project Manager III", sector="HEALTHCARE")
    assert prog_mgr["canonical_band"] == "B3_SENIOR_IC"
    assert prog_mgr["is_non_people_manager_track"] is True


# --------------------------------------------------------------------------- #
# Job Opening Level Neutralization
# --------------------------------------------------------------------------- #
def test_job_level_neutralization():
    senior_jd = {"job_title": "Senior Full-Stack Engineer", "level": "Senior"}
    neut_senior = neutralize_job_level(senior_jd, sector="FINANCIAL_SERVICES")
    assert neut_senior["canonical_band"] == "B3_SENIOR_IC"
    assert neut_senior["band_number"] == 3

    devops_jd = {"job_title": "DevOps Engineer", "level": "Not Available"}
    neut_devops = neutralize_job_level(devops_jd, sector="TECHNOLOGY")
    assert neut_devops["canonical_band"] == "B2_MID_IC"
    assert neut_devops["band_number"] == 2

    staff_jd = {"job_title": "Staff Azure Cloud Engineer, Automation", "level": "Staff"}
    neut_staff = neutralize_job_level(staff_jd, sector="PROFESSIONAL_SERVICES")
    assert neut_staff["canonical_band"] == "B3_SENIOR_IC"
    assert neut_staff["band_number"] == 3


# --------------------------------------------------------------------------- #
# Relative Reach Calculus
# --------------------------------------------------------------------------- #
def test_relative_reach_peer_and_technical_evaluator():
    """Delta = 0 represents a peer or technical evaluator, not a line hiring manager."""
    reach = calculate_relative_reach(
        person_band=3,
        job_band=3,
        size_tier="ENTERPRISE",
        sector="FINANCIAL_SERVICES",
    )
    assert reach["delta"] == 0
    assert reach["classification"] == "PEER_OR_KEY_TECHNICAL_INFLUENCER"
    assert reach["is_structurally_plausible_hiring_manager"] is False
    assert reach["hiring_manager_recommendation"] == "AGAINST_LINE_HM_PLAUSIBLE_INTERVIEWER"


def test_relative_reach_enterprise_executive_distance():
    """In Enterprise (10,001+), executives at Delta >= +3 are too distant."""
    reach = calculate_relative_reach(
        person_band=6,  # Managing Director
        job_band=3,     # Senior Full-Stack Engineer
        size_tier="ENTERPRISE",
        sector="FINANCIAL_SERVICES",
    )
    assert reach["delta"] == 3
    assert reach["classification"] == "TOO_DISTANT_EXECUTIVE"
    assert reach["is_structurally_plausible_hiring_manager"] is False
    assert reach["hiring_manager_recommendation"] == "AGAINST"


def test_relative_reach_enterprise_line_manager():
    """In Enterprise, a people manager at Delta = +1 is structurally plausible."""
    reach = calculate_relative_reach(
        person_band=4,  # Software Engineering Manager
        job_band=3,     # Senior Full Stack Engineer
        size_tier="ENTERPRISE",
        management_status="PEOPLE_MANAGER",
    )
    assert reach["delta"] == 1
    assert reach["classification"] == "STRUCTURALLY_PLAUSIBLE_LINE_MANAGER"
    assert reach["is_structurally_plausible_hiring_manager"] is True
    assert reach["hiring_manager_recommendation"] == "FOR"


def test_relative_reach_startup_and_small_company():
    """At small and growth companies, owning function heads / CTOs are plausible at Delta >= +3."""
    reach = calculate_relative_reach(
        person_band=8,  # Co-Founder & CTO
        job_band=2,     # DevOps Engineer
        size_tier="SMALL",
        is_owning_function_head=True,
    )
    assert reach["delta"] == 6
    assert reach["classification"] == "STARTUP_OR_GROWTH_FUNCTION_HEAD"
    assert reach["is_structurally_plausible_hiring_manager"] is True
    assert reach["hiring_manager_recommendation"] == "FOR"


def test_relative_reach_non_people_manager_track():
    """Program/Project managers at large companies coordinate but do not own hiring."""
    reach = calculate_relative_reach(
        person_band=3,
        job_band=2,
        size_tier="LARGE",
        is_non_people_manager_track=True,
    )
    assert reach["classification"] == "NON_PEOPLE_MANAGER_TRACK"
    assert reach["is_structurally_plausible_hiring_manager"] is False
    assert reach["hiring_manager_recommendation"] == "AGAINST_LINE_HM_PLAUSIBLE_INFLUENCER"


# --------------------------------------------------------------------------- #
# Management Evidence Extraction
# --------------------------------------------------------------------------- #
def test_management_evidence_ic_detection():
    """Profile describing hands-on IC architecture is recognized as individual contributor."""
    cand = {
        "summary": "Vice President, Software Engineering",
        "experiences": [
            {
                "title": "Vice President, Software Engineering",
                "company": "BNY",
                "description": "Architected and enhanced an enterprise-scale Angular UI component library with Storybook integration.",
            }
        ],
    }
    mgmt = extract_management_evidence(cand)
    assert mgmt["management_status_hint"] == "INDIVIDUAL_CONTRIBUTOR"
    assert "architected" in mgmt["individual_contributor_cues"]
    assert mgmt["evidenced_team_size"] is None


def test_management_evidence_leadership_detection():
    """Profile describing direct reports and team oversight is recognized as people manager."""
    cand = {
        "summary": "Engineering leader",
        "experiences": [
            {
                "title": "Engineering Director",
                "company": "Acme",
                "description": "Managed team of 25 engineers across core platform and infrastructure.",
            }
        ],
    }
    mgmt = extract_management_evidence(cand)
    assert mgmt["management_status_hint"] == "PEOPLE_MANAGER"
    assert mgmt["evidenced_team_size"] == 25


# --------------------------------------------------------------------------- #
# Integration with Real Datasets
# --------------------------------------------------------------------------- #
def test_real_dataset_bny_cases():
    """Verifies that Dmitry S. and Hillary Langat at BNY produce calibrated signals."""
    if not REAL_20_PATH.exists():
        pytest.skip("Real 20 datasets file not found.")

    data = json.loads(REAL_20_PATH.read_text(encoding="utf-8"))

    # Case 10: Dmitry S. @ BNY
    dmitry = data[9]
    signals_dmitry = derive_context_signals(
        dmitry["candidate_profile"], dmitry["job_description"], dmitry["company_context"]
    )
    assert signals_dmitry["sector"]["sector_hint"] == "FINANCIAL_SERVICES"
    assert signals_dmitry["company_size"]["size_tier"] == "ENTERPRISE"
    assert signals_dmitry["relative_reach"]["classification"] == "TOO_DISTANT_EXECUTIVE"
    assert signals_dmitry["relative_reach"]["hiring_manager_recommendation"] == "AGAINST"

    # Case 11: Hillary Langat @ BNY
    hillary = data[10]
    signals_hillary = derive_context_signals(
        hillary["candidate_profile"], hillary["job_description"], hillary["company_context"]
    )
    assert signals_hillary["sector"]["sector_hint"] == "FINANCIAL_SERVICES"
    assert signals_hillary["title_neutralization"]["candidate_canonical"]["is_corporate_rank_grade"] is True
    assert signals_hillary["title_neutralization"]["candidate_canonical"]["canonical_band"] == "B3_SENIOR_IC"
    assert signals_hillary["relative_reach"]["delta"] == 0
    assert signals_hillary["relative_reach"]["classification"] == "PEER_OR_KEY_TECHNICAL_INFLUENCER"
    assert signals_hillary["relative_reach"]["hiring_manager_recommendation"] == "AGAINST_LINE_HM_PLAUSIBLE_INTERVIEWER"
