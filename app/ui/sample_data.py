"""Realistic sample scenarios for hiring manager evaluation."""
import json

SCENARIO_STRONG_MATCH = {
    "candidate_profile": {
        "candidate_id": "EMP-84920",
        "full_name": "Elena Rostova",
        "current_title": "Director of Cloud Infrastructure",
        "current_department": "Core Platform Engineering",
        "tenure_at_company": "3 years 4 months",
        "direct_reports_count": 6,
        "total_team_size": 28,
        "budget_ownership": True,
        "key_responsibilities": [
            "Oversees Kubernetes clusters, multi-region AWS topology, and CI/CD pipelines",
            "Manages engineering managers and staff reliability engineers",
            "Responsible for hiring, performance evaluation, and team budget allocations across Cloud Platform"
        ]
    },
    "job_description": {
        "req_id": "REQ-2026-904",
        "title": "Staff Site Reliability Engineer (SRE)",
        "department": "Core Platform Engineering - Cloud Infrastructure",
        "reporting_to": "Director of Cloud Infrastructure",
        "level": "IC-6 / Staff",
        "target_start_date": "Q1 2027",
        "summary": "Seeking a Staff SRE to architect high-availability Kubernetes infrastructure and lead cloud resiliency initiatives.",
        "responsibilities": [
            "Drive zero-downtime architecture for mission-critical platform services",
            "Partner with cloud leadership to define operational SLAs and SLOs"
        ]
    },
    "company_context": {
        "company_name": "NovaScale Technologies",
        "headcount": 1400,
        "industry": "Enterprise Cloud Infrastructure",
        "org_structure": {
            "division": "Engineering & Technology",
            "department": "Core Platform Engineering",
            "hierarchy": [
                {"role": "VP of Infrastructure & Security"},
                {"role": "Director of Cloud Infrastructure", "hiring_authority_for": ["Staff SRE", "Principal Platform Engineer", "DevOps Manager"]},
                {"role": "Engineering Manager - SRE"}
            ]
        },
        "hiring_policy": "All Staff and Principal IC openings must be owned and interviewed by the divisional Director as designated hiring manager."
    }
}

SCENARIO_DISPUTED_MATCH = {
    "candidate_profile": {
        "candidate_id": "EMP-41029",
        "full_name": "Marcus Vance",
        "current_title": "Senior Product Manager - Growth",
        "current_department": "Consumer Growth & Monetization",
        "tenure_at_company": "11 months",
        "direct_reports_count": 0,
        "total_team_size": 0,
        "budget_ownership": False,
        "key_responsibilities": [
            "Drives user conversion funnels and checkout A/B testing",
            "Coordinates cross-functional sprint goals with mobile engineering squad"
        ]
    },
    "job_description": {
        "req_id": "REQ-2026-411",
        "title": "Senior Backend Security Engineer",
        "department": "Information Security & Cryptography",
        "reporting_to": "Head of Information Security",
        "level": "IC-5",
        "summary": "Core security engineering role implementing hardware security modules (HSM) and internal cryptographic auth protocols."
    },
    "company_context": {
        "company_name": "NovaScale Technologies",
        "headcount": 1400,
        "org_structure": {
            "division": "Security & Trust",
            "hiring_rules": "Security engineering roles report strictly to InfoSec leadership. Product managers have no hiring manager jurisdiction outside Growth PM roles."
        }
    }
}

