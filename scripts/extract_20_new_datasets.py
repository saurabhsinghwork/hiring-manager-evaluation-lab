import os
import urllib.parse
from pymongo import MongoClient
from bson import ObjectId
import json
from pathlib import Path

# Connect to MongoDB staging (STRICTLY READ-ONLY)
uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI")
if not uri:
    user = urllib.parse.quote_plus(os.getenv('MONGO_USERNAME', ''))
    pwd = urllib.parse.quote_plus(os.getenv('MONGO_PASSWORD', ''))
    cluster = os.getenv('MONGO_CLUSTER_URL', '')
    if user and pwd and cluster:
        uri = f'mongodb+srv://{user}:{pwd}@{cluster}'
    else:
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

    if cname.lower() in ('technology company', 'unknown', 'stealth', 'voyspark'):
        continue

    jd_desc = pjd.get('description') or {}
    jd_pos = pjd.get('position') or {}
    resps = jd_desc.get('responsibilities') or []
    reqs = jd_desc.get('requirements') or []

    # Require full, rich job descriptions with multiple responsibilities and requirements
    if len(resps) < 4 or len(reqs) < 4:
        continue

    exps = person.get('experiences') or []
    if not exps or len(exps) == 0:
        continue

    if company_counts.get(cname, 0) >= 2:
        continue

    seen_names.add(p_name.strip())
    company_counts[cname] = company_counts.get(cname, 0) + 1

    # 1. CANDIDATE PROFILE (All real values from MongoDB without omissions)
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

    # Clean skills (strings only)
    raw_skills = person.get('skills') or []
    clean_skills = []
    for s in raw_skills:
        if isinstance(s, dict):
            clean_skills.append(s.get('name') or str(s))
        elif isinstance(s, str):
            clean_skills.append(s)

    candidate_profile = {
        'candidate_name': p_name.strip(),
        'current_title': person.get('sub_headline') or person.get('headline') or '',
        'location': person.get('location') or '',
        'summary': person.get('about') or person.get('headline') or '',
        'experiences': formatted_exps,
        'skills': clean_skills
    }
    if person.get('education') or person.get('educations'):
        candidate_profile['education'] = person.get('education') or person.get('educations')

    # 2. JOB DESCRIPTION (All parsed JD fields from MongoDB)
    jd_skills_raw = jd_desc.get('skills') or []
    jd_skills = []
    for s in jd_skills_raw:
        if isinstance(s, dict):
            jd_skills.append(s.get('name') or str(s))
        elif isinstance(s, str):
            jd_skills.append(s)

    job_description = {
        'job_title': job.get('title') or jd_pos.get('full_title') or jd_pos.get('main_title') or '',
        'department': jd_pos.get('department') or '',
        'level': jd_pos.get('level') or '',
        'location': job.get('location') or (jd_desc.get('locations') if isinstance(jd_desc.get('locations'), str) else ''),
        'employment_type': jd_desc.get('employment_type') or '',
        'remote_type': jd_desc.get('remote_type') or '',
        'salary': jd_desc.get('salary') or '',
        'summary': jd_desc.get('summary') or job.get('description') or '',
        'key_responsibilities': resps,
        'requirements': reqs,
        'skills': jd_skills
    }
    if jd_desc.get('core_keywords'):
        job_description['core_keywords'] = jd_desc.get('core_keywords')
    if jd_desc.get('benefits'):
        job_description['benefits'] = jd_desc.get('benefits')

    # 3. COMPANY CONTEXT (All company fields from MongoDB)
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
        'candidate_profile': candidate_profile,
        'job_description': job_description,
        'company_context': company_context
    })

    print(f"Extracted #{len(datasets)}: {p_name.strip()} | {job_description['job_title']} @ {company_context['company_name']} (Resps: {len(resps)}, Reqs: {len(reqs)})")

    if len(datasets) >= 20:
        break

output_file = Path('C:/Users/Admin/Desktop/hiring-manager-evaluation-lab/data/samples/new_20_real_datasets.json')
output_file.parent.mkdir(parents=True, exist_ok=True)
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(datasets, f, indent=2)

print(f"\nCOMPLETED: Successfully extracted {len(datasets)} datasets to {output_file}")
