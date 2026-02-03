from __future__ import annotations

from typing import Dict

from ..scrapers.base_scraper import JobOffer


def build_scoring_prompt(job: JobOffer, profile: Dict) -> str:
    profile_summary = _build_profile_summary(profile)
    description = job.description[:2000] if job.description else ""

    return (
        "Evaluate this job offer for a Data Analyst Power BI (2 years exp, Paris, CDI).\n\n"
        f"OFFER:\n- Title: {job.title}\n- Company: {job.company}\n- Location: {job.location}\n"
        f"- Contract: {job.contract_type}\n- Description: {description}\n\n"
        f"CANDIDATE PROFILE:\n{profile_summary}\n\n"
        'Reply in JSON: {"score": 0-100, "reasoning": "..."}'
    )


def _build_profile_summary(profile: Dict) -> str:
    skills = profile.get("skills", {})
    required = ", ".join([item.get("keyword", "") for item in skills.get("required", [])])
    important = ", ".join([item.get("keyword", "") for item in skills.get("important", [])])
    not_known = ", ".join([item.get("keyword", "") for item in skills.get("not_known", [])])
    search = profile.get("search", {})
    company_types = ", ".join(search.get("company_types_preferred", []))

    lines = []
    if required:
        lines.append(f"- Required: {required}")
    if important:
        lines.append(f"- Important: {important}")
    if not_known:
        lines.append(f"- Not known: {not_known}")
    if company_types:
        lines.append(f"- Preferred companies: {company_types}")

    return "\n".join(lines) if lines else "- Profile not configured"
