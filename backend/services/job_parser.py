"""Fast deterministic job parsing and matching helpers.

These helpers intentionally avoid one-LLM-call-per-job. SerpAPI already returns
structured fields such as job_highlights and detected_extensions, so we use them
first and fall back to lightweight regex/keyword extraction from description.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

TECH_KEYWORDS = [
    "Python", "Java", "JavaScript", "TypeScript", "C#", "C++", "PHP", "Ruby", "Go", "Golang",
    "Kotlin", "Swift", "Dart", "Scala", "R", "MATLAB", "SQL", "NoSQL", "HTML", "HTML5", "CSS", "CSS3",
    "React", "Angular", "Vue", "Next.js", "Nuxt", "Node.js", "Express", "NestJS", "Spring", "Spring Boot",
    "Django", "Flask", "FastAPI", "Laravel", ".NET", "ASP.NET", "VB.NET", "REST", "REST API", "GraphQL",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Oracle", "SQLite", "Supabase", "Firebase", "Prisma",
    "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Google Cloud", "CI/CD", "Git", "GitHub", "GitLab",
    "Jenkins", "Linux", "Bash", "PowerShell", "Agile", "Scrum", "Jira", "Figma", "UI/UX",
    "Machine Learning", "Deep Learning", "AI", "LLM", "NLP", "Computer Vision", "TensorFlow", "PyTorch",
    "scikit-learn", "Pandas", "NumPy", "Excel", "Power BI", "Tableau", "Data Analysis", "Data Visualization",
    "ETL", "Testing", "Unit Testing", "Selenium", "Cypress", "Playwright", "QA", "Cybersecurity",
]

SOFT_KEYWORDS = [
    "Communication", "Teamwork", "Leadership", "Problem Solving", "Analytical", "Critical Thinking",
    "Collaboration", "Time Management", "Adaptability", "Attention to Detail", "Creativity", "Presentation",
    "Stakeholder Management", "Customer Service", "Documentation", "Self-motivated", "Independent",
]

CURRENCY_MAP = {
    "RM": "MYR", "MYR": "MYR", "$": "USD", "USD": "USD", "US$": "USD", "S$": "SGD", "SGD": "SGD",
    "CA$": "CAD", "CAD": "CAD", "A$": "AUD", "AUD": "AUD", "£": "GBP", "GBP": "GBP", "€": "EUR", "EUR": "EUR",
    "₹": "INR", "INR": "INR", "¥": "JPY", "JPY": "JPY", "R$": "BRL", "BRL": "BRL",
}

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.\-/]*")


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_as_text(v) for v in value)
    if isinstance(value, dict):
        return "\n".join(_as_text(v) for v in value.values())
    return str(value)


def _clean_item(text: str, max_len: int = 220) -> str:
    text = re.sub(r"\s+", " ", text or "").strip(" •-–—\t\n")
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def _dedupe(items: Iterable[str], limit: int | None = None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = _clean_item(str(item))
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
        if limit and len(out) >= limit:
            break
    return out


def _highlight_items(job: dict[str, Any], title_contains: tuple[str, ...]) -> list[str]:
    items: list[str] = []
    for group in job.get("job_highlights") or []:
        group_title = str(group.get("title") or "").lower()
        if any(needle in group_title for needle in title_contains):
            items.extend(group.get("items") or [])
    return _dedupe(items)


def _contains_keyword(text: str, keyword: str) -> bool:
    # Keep symbols such as C++, C#, .NET usable while avoiding broad substring mistakes.
    escaped = re.escape(keyword.lower())
    if re.search(r"[+#.]", keyword):
        return escaped in text.lower()
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text.lower()) is not None


def extract_skills_from_text(text: str, keyword_bank: list[str], limit: int = 12) -> list[str]:
    found = [kw for kw in keyword_bank if _contains_keyword(text, kw)]
    return _dedupe(found, limit=limit)


def extract_responsibilities(job: dict[str, Any]) -> list[str]:
    highlighted = _highlight_items(job, ("responsibil", "what you", "duties", "role"))
    if highlighted:
        return _dedupe(highlighted, limit=5)

    description = _as_text(job.get("description"))
    sentences = re.split(r"(?<=[.!?])\s+|\n+|•", description)
    action_words = (
        "develop", "build", "design", "maintain", "support", "collaborate", "implement", "analyze",
        "test", "debug", "manage", "create", "prepare", "assist", "work", "deliver", "write", "document",
    )
    candidates = [s for s in sentences if any(s.strip().lower().startswith(w) or f" {w}" in s.lower() for w in action_words)]
    return _dedupe(candidates, limit=5)


def extract_education(text: str) -> str | None:
    patterns = [
        r"(Bachelor(?:'s)?(?: Degree)?[^.;\n]{0,90})",
        r"(Degree in [^.;\n]{0,90})",
        r"(Diploma in [^.;\n]{0,90})",
        r"(Master(?:'s)?(?: Degree)?[^.;\n]{0,90})",
        r"(PhD[^.;\n]{0,90})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_item(match.group(1), max_len=140)
    return None


def extract_min_years(text: str) -> int:
    patterns = [
        r"(\d+)\+?\s*(?:years|yrs)\s+(?:of\s+)?(?:relevant\s+)?experience",
        r"minimum\s+(?:of\s+)?(\d+)\s*(?:years|yrs)",
        r"at\s+least\s+(\d+)\s*(?:years|yrs)",
    ]
    years: list[int] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            try:
                years.append(int(match.group(1)))
            except ValueError:
                pass
    return min(years) if years else 0


def parse_salary(salary: Any, description: str = "") -> dict[str, Any] | None:
    salary_text = _as_text(salary)
    raw = salary_text or description[:800]
    if not raw:
        return None

    # Avoid misreading unrelated numbers such as years of experience as salary.
    # Description fallback is used only when the text has salary/pay/currency cues.
    if not salary_text and not re.search(r"salary|pay|compensation|wage|per month|per year|per hour|/hr|/month|/year|RM|MYR|USD|SGD|[$£€₹¥]", raw, flags=re.IGNORECASE):
        return None

    currency = None
    for symbol, code in CURRENCY_MAP.items():
        if symbol.lower() in raw.lower():
            currency = code
            break

    money_pattern = re.compile(
        r"(?:RM|MYR|US\$|S\$|CA\$|A\$|USD|SGD|CAD|AUD|GBP|EUR|INR|JPY|BRL|[$£€₹¥])?\s*"
        r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*([kKmM])?"
    )
    values: list[float] = []
    for match in money_pattern.finditer(raw):
        num = float(match.group(1).replace(",", ""))
        suffix = (match.group(2) or "").lower()
        if suffix == "k":
            num *= 1_000
        elif suffix == "m":
            num *= 1_000_000
        # Avoid treating years like 2026 as salary when no currency is present.
        if currency is None and 1900 <= num <= 2100:
            continue
        values.append(num)

    if not values:
        return None

    lowered = raw.lower()
    if any(x in lowered for x in ["hour", "/hr", " per hr", "hourly"]):
        period = "hourly"
    elif any(x in lowered for x in ["year", "annual", "annum", "pa", "p.a"]):
        period = "yearly"
    else:
        period = "monthly"

    min_salary = int(min(values))
    max_salary = int(max(values))
    return {
        "min_salary": min_salary,
        "max_salary": max_salary,
        "currency": currency,
        "pay_period": period,
    }


def _first_apply_link(job: dict[str, Any]) -> str | None:
    apply_options = job.get("apply_options") or []
    if isinstance(apply_options, list) and apply_options:
        link = apply_options[0].get("link") or apply_options[0].get("apply_link")
        if link:
            return link
    related_links = job.get("related_links") or []
    if isinstance(related_links, list) and related_links:
        return related_links[0].get("link")
    return job.get("source_link") or job.get("share_link")


def normalise_job_record(job: dict[str, Any], target_role: str | None = None) -> dict[str, Any]:
    title = _clean_item(job.get("title") or "Untitled Job", max_len=180)
    company_name = _clean_item(job.get("company_name") or job.get("company") or "Unknown Company", max_len=160)
    description = _as_text(job.get("description"))

    highlights_text = _as_text(job.get("job_highlights"))
    combined_text = "\n".join([title, company_name, description, highlights_text, _as_text(job.get("extensions"))])

    job_id = job.get("job_id")
    if not job_id:
        unique_key = f"{title}|{company_name}|{job.get('location')}|{description[:180]}"
        job_id = hashlib.md5(unique_key.encode("utf-8")).hexdigest()

    qualification_items = _highlight_items(job, ("qualification", "requirement", "skills", "minimum"))
    existing_responsibilities = job.get("key_responsibilities") or []
    responsibility_items = _dedupe(existing_responsibilities, limit=5) or extract_responsibilities(job)

    existing_core = job.get("core_skills") or []
    existing_soft = job.get("soft_skills") or []
    core_skills = _dedupe(existing_core, limit=12) or extract_skills_from_text("\n".join(qualification_items) + "\n" + combined_text, TECH_KEYWORDS, limit=12)
    soft_skills = _dedupe(existing_soft, limit=8) or extract_skills_from_text("\n".join(qualification_items) + "\n" + combined_text, SOFT_KEYWORDS, limit=8)

    detected = job.get("detected_extensions") or {}
    salary = detected.get("salary") or job.get("salary")
    salary_parsed = job.get("salary_parsed") or parse_salary(salary, combined_text)

    clean_job = {
        "target_job_role": target_role or job.get("target_job_role") or "General",
        "job_id": str(job_id),
        "title": title,
        "company_name": company_name,
        "location": job.get("location") or "",
        "via": job.get("via"),
        "posted_at": detected.get("posted_at"),
        "salary": salary,
        "salary_parsed": salary_parsed,
        "work_from_home": detected.get("work_from_home", job.get("work_from_home")),
        "schedule_type": detected.get("schedule_type", job.get("schedule_type")),
        "source_link": _first_apply_link(job),
        "share_link": job.get("share_link"),
        "description": description,
        "key_responsibilities": responsibility_items,
        "core_skills": core_skills,
        "soft_skills": soft_skills,
        "minimum_years_experience": job.get("minimum_years_experience") or extract_min_years(combined_text),
        "education_requirement": job.get("education_requirement") or extract_education(combined_text),
        "extraction_method": "serpapi_fast_parser",
    }

    # Preserve useful raw SerpAPI structures for future debugging/UI without bloating too much.
    if job.get("job_highlights"):
        clean_job["job_highlights"] = job.get("job_highlights")
    if job.get("apply_options"):
        clean_job["apply_options"] = job.get("apply_options")

    return clean_job


def normalize_for_match(text: Any) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(_as_text(text)) if len(token) >= 2}


def _skill_match(candidate_text: str, skill: str) -> bool:
    if not skill:
        return False
    skill_lower = skill.lower()
    candidate_lower = candidate_text.lower()
    if skill_lower in candidate_lower:
        return True
    skill_tokens = normalize_for_match(skill_lower)
    candidate_tokens = normalize_for_match(candidate_lower)
    if not skill_tokens:
        return False
    # For multi-token skills, require most tokens. For single-token skills, require exact token.
    required = max(1, int(len(skill_tokens) * 0.67 + 0.5))
    return len(skill_tokens & candidate_tokens) >= required


def _target_role_score(user_data: dict[str, Any], job: dict[str, Any]) -> float:
    roles = user_data.get("target_job_roles") or user_data.get("growth_intent") or []
    title_text = f"{job.get('title', '')} {job.get('target_job_role', '')}".lower()
    if not roles:
        return 0.5
    best = 0.0
    for role in roles:
        role_tokens = normalize_for_match(role)
        if not role_tokens:
            continue
        overlap = len(role_tokens & normalize_for_match(title_text)) / max(1, len(role_tokens))
        best = max(best, overlap)
    return min(1.0, best)


def fast_rank_jobs(user_data: dict[str, Any], jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score jobs locally in milliseconds and return descending order.

    The score is intentionally explainable: skills fit, target-role fit, experience,
    salary, and job-type/context are all visible in the returned fields.
    """
    if not user_data:
        return jobs

    candidate_skills = []
    for key in ("primary_competencies", "secondary_competencies", "operational_style", "languages"):
        value = user_data.get(key) or []
        candidate_skills.extend(value if isinstance(value, list) else [value])
    for exp in user_data.get("experience_and_projects") or []:
        if isinstance(exp, dict):
            candidate_skills.extend(exp.get("technologies") or [])
            candidate_skills.append(exp.get("title") or "")
            candidate_skills.append(exp.get("context") or "")
    candidate_text = "\n".join(_as_text(x) for x in candidate_skills)
    candidate_years = float(user_data.get("years_of_experience") or 0)
    expected_salary = int(user_data.get("expected_salary") or 0)

    ranked: list[dict[str, Any]] = []
    for job in jobs:
        normalised = normalise_job_record(job, job.get("target_job_role"))
        core_skills = normalised.get("core_skills") or []
        soft_skills = normalised.get("soft_skills") or []

        matched_core = [skill for skill in core_skills if _skill_match(candidate_text, skill)]
        missing_core = [skill for skill in core_skills if skill not in matched_core]
        matched_soft = [skill for skill in soft_skills if _skill_match(candidate_text, skill)]

        if core_skills:
            skill_score = len(matched_core) / len(core_skills)
        else:
            # If no explicit skills were extractable, use target-title overlap as a neutral proxy.
            skill_score = 0.55

        role_score = _target_role_score(user_data, normalised)

        min_exp = int(normalised.get("minimum_years_experience") or 0)
        if min_exp <= 0:
            exp_score = 1.0
        elif candidate_years >= min_exp:
            exp_score = 1.0
        else:
            exp_score = max(0.0, candidate_years / max(1, min_exp))

        salary_score = 1.0
        salary_parsed = normalised.get("salary_parsed") or {}
        max_salary = salary_parsed.get("max_salary") or salary_parsed.get("min_salary")
        if expected_salary and max_salary:
            salary_score = 1.0 if max_salary >= expected_salary else max(0.0, max_salary / expected_salary)

        # Internships should not be punished heavily for low professional experience.
        schedule_text = f"{normalised.get('schedule_type') or ''} {normalised.get('title') or ''}".lower()
        is_internship = "intern" in schedule_text
        if is_internship and candidate_years < 1:
            exp_score = max(exp_score, 0.9)

        score = (skill_score * 45) + (role_score * 25) + (exp_score * 15) + (salary_score * 10)
        if normalised.get("work_from_home"):
            score += 2
        if normalised.get("description"):
            score += 3
        logical_match_score = int(round(max(0, min(100, score))))

        missing_resp: list[str] = []
        if logical_match_score < 65:
            missing_resp = (normalised.get("key_responsibilities") or [])[:2]

        if missing_core:
            gap_text = f"Missing core skills: {', '.join(missing_core[:4])}."
        else:
            gap_text = "No major extracted core-skill gaps were detected."
        if matched_core:
            strength_text = f"Matched skills include {', '.join(matched_core[:5])}."
        else:
            strength_text = "The role may still be relevant, but the extracted skills have limited direct overlap with the profile."

        normalised.update({
            "matched_mandatory_skills": matched_core,
            "unmatched_mandatory_skills": missing_core,
            "unmatched_responsibilities": missing_resp,
            "matched_optional_skills": matched_soft,
            "logical_match_score": logical_match_score,
            "has_dealbreaker_gap": False,
            "remap_description": f"{gap_text} {strength_text}",
            "matching_method": "fast_local_remap",
        })
        ranked.append(normalised)

    ranked.sort(key=lambda x: x.get("logical_match_score", 0), reverse=True)
    return ranked
