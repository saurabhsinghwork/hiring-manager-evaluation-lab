import os
from pymongo import MongoClient
from bson import ObjectId
import json
from pathlib import Path

# Connect to MongoDB staging (STRICTLY READ-ONLY). Keep credentials out of source control.
uri = os.environ.get("MONGODB_URI")
if not uri:
    raise RuntimeError("Set MONGODB_URI in the environment before running this script.")

client = MongoClient(uri, serverSelectionTimeoutMS=10000)
db = client['hp_data']

# Exclude initial 10 candidates already present in staging_real_datasets.json
existing_names = {
    'Yanxing Wang', 'Alex McLeod', 'Kallol Das', 'Ryan Rauh', 
    'Nathan Andrews', 'Adam W. Lerman', 'William Jenkins', 
    'Jordan Floyd', 'Anthony Gravell', 'Nicholas Dykzeul'
}

datasets = []
seen_names = set(existing_names)
company_counts = {}

# Target a wide variety of top real companies from MongoDB
links = list(db['hm_job_profile_links'].find())

for l in links:
    person = db['people_details'].find_one({'_id': l.get('person_id')}) or db['people_details'].find_one({'username': l.get('username')})
    if not person:
        continue
    p_name = person.get('name')
    if not p_name or p_name.strip() in seen_names:
        continue

    job = db['jobs'].find_one({'_id': l.get('hm_job_id')})
    if not job:
        continue

    pjd = job.get('parsed_job_description') or {}
    hiring_comp = pjd.get('hiring_company') or {}

    # Company name resolution
    comp_doc = None
    if job.get('company_id'):
        cid = job.get('company_id')
        try:
            comp_doc = db['company_information'].find_one({'_id': ObjectId(str(cid))}) or db['company_information'].find_one({'_id': str(cid)})
        except Exception:
            pass

    cname = (comp_doc.get('name') if comp_doc else None) or hiring_comp.get('name')
    if not cname:
        continue
    cname = cname.strip()

    if not comp_doc:
        comp_doc = db['company_information'].find_one({'name': {'$regex': f'^{cname}$', '$options': 'i'}}) or db['company_information'].find_one({'name': {'$regex': cname, '$options': 'i'}}) or {}

    # Skip generic placeholder companies
    if cname.lower() in ('technology company', 'unknown', 'stealth'):
        continue

    # Ensure rich job description with real responsibilities
    jd_desc = pjd.get('description') or {}
    jd_pos = pjd.get('position') or {}
    resps = jd_desc.get('responsibilities') or []
    reqs = jd_desc.get('requirements') or []

    # Ensure candidate has experiences
    exps = person.get('experiences') or []
    if not exps:
        continue

    # Limit to at most 2 candidates per company to ensure diversity
    if company_counts.get(cname, 0) >= 2:
        continue

    seen_names.add(p_name.strip())
    company_counts[cname] = company_counts.get(cname, 0) + 1

    # 1. CANDIDATE PROFILE (Raw values directly as they are in MongoDB)
    formatted_exps = []
    for exp in exps:
        if isinstance(exp, dict):
            formatted_exps.append({
                'title': exp.get('title') or exp.get('role') or '',
                'company': exp.get('company') or exp.get('company_name') or '',
                'duration': exp.get('duration') or exp.get('date_range') or '',
                'location': exp.get('location') or '',
                'description': exp.get('description') or ''
            })

    hr_profile = {
        'candidate_name': p_name.strip(),
        'current_title': person.get('sub_headline') or person.get('headline') or '',
        'location': person.get('location') or '',
        'summary': person.get('about') or person.get('headline') or '',
        'experiences': formatted_exps,
        'skills': person.get('skills') or []
    }
    if person.get('education') or person.get('educations'):
        hr_profile['education'] = person.get('education') or person.get('educations')

    # 2. JOB DESCRIPTION (Raw values directly as they are in MongoDB without changes)
    job_description = {
        'job_title': job.get('title') or jd_pos.get('full_title') or jd_pos.get('main_title') or '',
        'department': jd_pos.get('department') or '',
        'level': jd_pos.get('level') or '',
        'location': job.get('location') or (jd_desc.get('locations') if isinstance(jd_desc.get('locations'), str) else ''),
        'employment_type': jd_desc.get('employment_type') or '',
        'summary': jd_desc.get('summary') or job.get('description') or '',
        'key_responsibilities': resps,
        'requirements': reqs,
        'skills': jd_desc.get('skills') or []
    }
    if jd_desc.get('core_keywords'):
        job_description['core_keywords'] = jd_desc.get('core_keywords')
    if jd_desc.get('other_information'):
        job_description['other_information'] = jd_desc.get('other_information')
    if jd_desc.get('benefits'):
        job_description['benefits'] = jd_desc.get('benefits')

    # 3. COMPANY CONTEXT (Raw values directly as they are in MongoDB without changes)
    company_context = {
        'company_name': (comp_doc.get('name') if comp_doc else None) or cname,
        'industry': (comp_doc.get('industry') if comp_doc else None) or hiring_comp.get('industry') or '',
        'company_size': (comp_doc.get('company_size') if comp_doc else None) or hiring_comp.get('size') or '',
        'website': (comp_doc.get('company_website') if comp_doc else None) or hiring_comp.get('website') or '',
        'headquarters': (comp_doc.get('headquarter') if comp_doc else None) or '',
        'founding_year': (comp_doc.get('founding_year') if comp_doc else None) or '',
        'company_overview': (comp_doc.get('overview') if comp_doc else None) or '',
        'specialties': (comp_doc.get('specialties') if comp_doc else None) or ''
    }

    datasets.append({
        'dataset_id': len(datasets) + 1,
        'candidate_name': p_name.strip(),
        'target_job': job_description['job_title'],
        'company': company_context['company_name'],
        'hr_profile': hr_profile,
        'candidate_profile': hr_profile,
        'job_description': job_description,
        'company_context': company_context
    })

    print(f"Extracted #{len(datasets)}: {p_name.strip()} | {job_description['job_title']} @ {company_context['company_name']}")

    if len(datasets) >= 20:
        break

output_file = Path('C:/Users/Admin/Desktop/hiring-manager-evaluation-lab/data/samples/new_20_real_datasets.json')
output_file.parent.mkdir(parents=True, exist_ok=True)
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(datasets, f, indent=2)

print(f"\nCOMPLETED: Successfully extracted {len(datasets)} datasets to {output_file}")
