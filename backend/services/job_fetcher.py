import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import serpapi
from core.config import settings
from services.job_parser import normalise_job_record

client = serpapi.Client(api_key=settings.SERPAPI_API_KEY)

MAX_JOBS_PER_REQUEST = max(1, int(getattr(settings, "JOB_SEARCH_MAX_RESULTS", 12) or 12))
MAX_ROLES_PER_SEARCH = max(1, int(getattr(settings, "JOB_SEARCH_MAX_ROLES", 3) or 3))
SERPAPI_TIMEOUT_SECONDS = int(getattr(settings, "SERPAPI_TIMEOUT_SECONDS", 25) or 25)
DATE_CHIP = getattr(settings, "JOB_SEARCH_DATE_CHIP", "date_posted:month") or "date_posted:month"

_executor = ThreadPoolExecutor(max_workers=MAX_ROLES_PER_SEARCH)


def _dedupe_roles(roles: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for role in roles or []:
        role = " ".join(str(role or "").split())
        if not role:
            continue
        key = role.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(role)
        if len(cleaned) >= MAX_ROLES_PER_SEARCH:
            break
    return cleaned


def _build_query(job_role: str, state: str | None, country: str, is_intern: bool) -> str:
    role = job_role.strip()
    parts = [role]
    if is_intern and "intern" not in role.lower():
        parts.append("internship")
    parts.append("jobs")
    if state:
        parts.append(f"in {state}")
    elif country:
        parts.append(f"in {country}")
    return " ".join(parts)


def search_single_role(job_role: str, country: str, country_abbr: str, state: str | None, is_intern: bool) -> dict[str, Any]:
    location = f"{state}, {country}" if state else country
    params = {
        "engine": "google_jobs",
        "q": _build_query(job_role, state, country, is_intern),
        "location": location,
        "google_domain": "google.com",
        "gl": country_abbr,
        "hl": "en",
    }
    # Date chips reduce stale/noisy results. If Google returns no results with chips,
    # fetch_job_list will automatically retry without it.
    if DATE_CHIP:
        params["chips"] = DATE_CHIP
    return client.search(params)


def _search_single_role_no_chip(job_role: str, country: str, country_abbr: str, state: str | None, is_intern: bool) -> dict[str, Any]:
    location = f"{state}, {country}" if state else country
    return client.search({
        "engine": "google_jobs",
        "q": _build_query(job_role, state, country, is_intern),
        "location": location,
        "google_domain": "google.com",
        "gl": country_abbr,
        "hl": "en",
    })


async def _run_search_with_timeout(loop, fn, *args):
    return await asyncio.wait_for(loop.run_in_executor(_executor, fn, *args), timeout=SERPAPI_TIMEOUT_SECONDS)


async def fetch_job_list(target_job_role: list[str], country: str, country_abbr: str, state: str | None = None, is_intern: bool = False):
    all_clean_match_jobs: list[dict[str, Any]] = []
    seen_job_ids: set[str] = set()
    roles = _dedupe_roles(target_job_role)

    if not roles:
        return []

    loop = asyncio.get_running_loop()

    # Fire a small number of SerpAPI searches concurrently. This keeps the total
    # search phase usually within seconds instead of waiting role-by-role.
    results = await asyncio.gather(*[
        _run_search_with_timeout(loop, search_single_role, role, country, country_abbr, state, is_intern)
        for role in roles
    ], return_exceptions=True)

    # If date chips over-filtered a role, retry that role once without chips.
    retry_tasks = []
    retry_roles = []
    for role, result in zip(roles, results):
        if isinstance(result, Exception) or not (result or {}).get("jobs_results"):
            retry_roles.append(role)
            retry_tasks.append(_run_search_with_timeout(loop, _search_single_role_no_chip, role, country, country_abbr, state, is_intern))
    if retry_tasks:
        retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)
        retry_map = dict(zip(retry_roles, retry_results))
    else:
        retry_map = {}

    for role, matching_jobs in zip(roles, results):
        if len(all_clean_match_jobs) >= MAX_JOBS_PER_REQUEST:
            break

        if isinstance(matching_jobs, Exception) or not (matching_jobs or {}).get("jobs_results"):
            matching_jobs = retry_map.get(role)

        if isinstance(matching_jobs, Exception):
            print(f"Error fetching jobs for '{role}': {matching_jobs}")
            continue

        for job in (matching_jobs or {}).get("jobs_results", []):
            clean_job = normalise_job_record(job, target_role=role)
            job_id = clean_job.get("job_id")
            title = clean_job.get("title")
            company_name = clean_job.get("company_name")

            if not job_id or job_id in seen_job_ids:
                continue
            if not title or not company_name:
                continue

            seen_job_ids.add(job_id)
            all_clean_match_jobs.append(clean_job)
            if len(all_clean_match_jobs) >= MAX_JOBS_PER_REQUEST:
                break

    print(f"Successfully searched and parsed {len(all_clean_match_jobs)} jobs from SerpAPI")
    return all_clean_match_jobs[:MAX_JOBS_PER_REQUEST]
