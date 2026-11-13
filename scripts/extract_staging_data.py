import os
from pymongo import MongoClient
import json
from pathlib import Path

# MongoDB staging URI is supplied out of band; never store credentials in source control.
uri = os.environ.get("MONGODB_URI")
if not uri:
    raise RuntimeError("Set MONGODB_URI in the environment before running this script.")

client = MongoClient(uri, serverSelectionTimeoutMS=10000)
db = client['hp_data']

# Read-only query for linked records
links = list(db['hm_job_profile_links'].find().limit(60))
datasets = []
seen_names = set()

for l in links:
    job = db['jobs'].find_one({'_id': l.get('hm_job_id')})
    if not job:
        continue
    person = db['people_details'].find_one({'_id': l.get('person_id')}) or db['people_details'].find_one({'username': l.get('username')})
    if not person:
        continue

    p_name = person.get('name')
    if not p_name or p_name in seen_names:
        continue
    seen_names.add(p_name)
    
    parsed_jd = job.get('parsed_job_description', {}) or {}
    hiring_comp = parsed_jd.get('hiring_company', {}) or {}
    comp_name = hiring_comp.get('name') or 'Technology Company'
    
    # Try finding company info in company_information
    comp_doc = db['company_information'].find_one({'name': {'$regex': comp_name, '$options': 'i'}}) or {}
    
    # Extract experiences cleanly
    exps = []
    for exp in (person.get('experiences') or [])[:4]:
        if isinstance(exp, dict):
            exps.append({
                'title': exp.get('title') or exp.get('role') or 'Engineering Role',
                'company': exp.get('company') or exp.get('company_name') or comp_name,
                'duration': exp.get('duration') or exp.get('date_range') or '2 years',
                'description': (exp.get('description') or '')[:250]
            })

    # Candidate Profile JSON
    candidate_profile = {
        'candidate_name': p_name,
        'current_title': person.get('sub_headline') or person.get('headline') or 'Technology Leader',
        'location': person.get('location', 'United States'),
        'summary': (person.get('about') or person.get('headline') or 'Experienced leader with hands-on technical management background.')[:400],
        'experiences': exps,
        'skills': (person.get('skills') or [])[:8]
    }

    # Job Description JSON
    jd_desc = parsed_jd.get('description', {}) or {}
    jd_pos = parsed_jd.get('position', {}) or {}
    job_description = {
        'job_title': job.get('title', 'Software Engineer'),
        'department': jd_pos.get('department') or 'Engineering & Technology',
        'level': jd_pos.get('level') or 'Mid-Senior Level',
        'location': job.get('location') or 'Remote / Hybrid',
        'summary': (jd_desc.get('summary') or job.get('description', 'Role focuses on core development, system reliability, and cross-functional engineering deliverables.'))[:400],
        'key_responsibilities': (jd_desc.get('responsibilities') or [
            'Design and maintain scalable infrastructure and core service components.',
            'Collaborate with product and engineering managers on roadmap milestones.',
            'Participate in architecture reviews and code quality initiatives.'
        ])[:5],
        'requirements': (jd_desc.get('requirements') or [
            'Proven track record in software engineering or systems architecture.',
            'Strong communication and cross-functional team collaboration skills.'
        ])[:5]
    }

    # Company Context JSON
    company_context = {
        'company_name': comp_name,
        'industry': hiring_comp.get('industry') or comp_doc.get('industry') or 'Software Development & Technology',
        'company_size': hiring_comp.get('size') or comp_doc.get('company_size') or '50-500 employees',
        'website': hiring_comp.get('website') or comp_doc.get('company_website') or 'https://example.com',
        'company_overview': (comp_doc.get('overview') or f'{comp_name} provides specialized technology platforms and enterprise software services.')[:400],
        'organizational_structure': f'Engineering managers and functional directors oversee engineering requisitions and interview pipelines at {comp_name}.'
    }

    datasets.append({
        'dataset_id': len(datasets) + 1,
        'candidate_name': p_name,
        'target_job': job_description['job_title'],
        'company': comp_name,
        'candidate_profile': candidate_profile,
        'job_description': job_description,
        'company_context': company_context
    })

    if len(datasets) >= 10:
        break

output_file = Path('C:/Users/Admin/Desktop/hiring-manager-evaluation-lab/data/samples/staging_real_datasets.json')
output_file.parent.mkdir(parents=True, exist_ok=True)
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(datasets, f, indent=2)

print(f'SUCCESS: Extracted {len(datasets)} real test datasets from staging database into {output_file}')

