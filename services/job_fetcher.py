"""
Job Fetcher Service
===================
Source: JSearch via RapidAPI (Google Jobs) — best Pakistan coverage.
Fallback: sample jobs shown when RAPIDAPI_KEY is not configured.
"""
import requests
from config import Config


def fetch_jsearch_jobs(keywords, location='Pakistan', results=24):
    """Search Google Jobs via RapidAPI JSearch. Covers Pakistani listings."""
    if not Config.RAPIDAPI_KEY:
        return []

    loc_str = location if location.lower() not in ('all', '') else 'Pakistan'
    query   = f"{keywords} jobs in {loc_str}" if keywords else f"jobs in {loc_str}"

    headers = {
        "X-RapidAPI-Key":  Config.RAPIDAPI_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }
    params = {
        "query":       query,
        "num_pages":   "1",
        "date_posted": "all",
    }
    try:
        resp = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers=headers, params=params, timeout=12
        )
        resp.raise_for_status()
        data = resp.json()
        return [_normalize_jsearch(j) for j in data.get("data", [])[:results]]
    except Exception as e:
        print(f"[JSearch Error] {e}")
        return []


def _normalize_jsearch(job):
    city      = job.get("job_city", "") or ""
    country   = job.get("job_country", "") or ""
    loc_parts = [p for p in [city, country] if p]
    loc       = ", ".join(loc_parts) if loc_parts else (
        "Remote" if job.get("job_is_remote") else "Pakistan"
    )
    sal_min  = job.get("job_min_salary")
    sal_max  = job.get("job_max_salary")
    currency = job.get("job_salary_currency", "PKR")
    if sal_min and sal_max:
        salary = f"{currency} {int(sal_min):,}–{int(sal_max):,}"
    elif sal_min:
        salary = f"{currency} {int(sal_min):,}+"
    else:
        salary = "Salary not listed"

    return {
        "id":          f"jsearch_{job.get('job_id', '')}",
        "title":       job.get("job_title", ""),
        "company":     job.get("employer_name", "Unknown"),
        "location":    loc,
        "type":        job.get("job_employment_type", "Full-time").replace("_", " ").title(),
        "salary":      salary,
        "url":         job.get("job_apply_link", ""),
        "description": job.get("job_description", ""),
        "source":      "Google Jobs",
        "logo":        "🔍",
        "match":       0,
    }


def fetch_all_jobs(keywords, location='Pakistan', limit=24):
    """Fetch jobs from JSearch (RapidAPI). Falls back to sample jobs if no key."""
    jobs = fetch_jsearch_jobs(keywords, location=location, results=limit)

    # Deduplicate by title + company
    seen, unique = set(), []
    for j in jobs:
        key = (j['title'].strip().lower(), j['company'].strip().lower())
        if key not in seen and j['title']:
            seen.add(key)
            unique.append(j)

    return unique[:limit]


def get_sample_jobs():
    """Shown when RAPIDAPI_KEY is not configured."""
    return [
        {"id":"s1","title":"Electrical Engineer",        "company":"WAPDA",             "logo":"⚡","location":"Lahore, Pakistan",   "type":"Full-time","salary":"PKR 150k–220k/mo","url":"#","source":"sample","match":0,"description":"electrical power systems substation transformer relay plc scada"},
        {"id":"s2","title":"Power Systems Engineer",     "company":"K-Electric",        "logo":"🔋","location":"Karachi, Pakistan",  "type":"Full-time","salary":"PKR 180k–260k/mo","url":"#","source":"sample","match":0,"description":"power distribution substation high voltage transformer protection relay"},
        {"id":"s3","title":"Instrumentation Engineer",   "company":"Engro",             "logo":"🏭","location":"Karachi, Pakistan",  "type":"Full-time","salary":"PKR 160k–240k/mo","url":"#","source":"sample","match":0,"description":"plc scada hmi instrumentation control panel design"},
        {"id":"s4","title":"Electrical Design Engineer", "company":"NESPAK",            "logo":"📐","location":"Islamabad, Pakistan","type":"Full-time","salary":"PKR 140k–200k/mo","url":"#","source":"sample","match":0,"description":"autocad electrical drawings cable sizing lighting design panel design"},
        {"id":"s5","title":"Software Engineer",          "company":"Systems Ltd",       "logo":"💻","location":"Lahore, Pakistan",   "type":"Full-time","salary":"PKR 200k–280k/mo","url":"#","source":"sample","match":0,"description":"python java software development backend api"},
        {"id":"s6","title":"Data Analyst",               "company":"Jazz",              "logo":"📊","location":"Karachi, Pakistan",  "type":"Full-time","salary":"PKR 130k–180k/mo","url":"#","source":"sample","match":0,"description":"data analysis sql excel power bi tableau statistics"},
        {"id":"s7","title":"Civil Engineer",             "company":"FWO",               "logo":"🏗️","location":"Rawalpindi, Pakistan","type":"Full-time","salary":"PKR 120k–190k/mo","url":"#","source":"sample","match":0,"description":"structural design concrete foundation autocad revit etabs"},
        {"id":"s8","title":"Mechanical Engineer",        "company":"Atlas Honda",       "logo":"⚙️","location":"Lahore, Pakistan",   "type":"Full-time","salary":"PKR 140k–210k/mo","url":"#","source":"sample","match":0,"description":"mechanical design solidworks manufacturing production cnc autocad"},
    ]
