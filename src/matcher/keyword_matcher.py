from __future__ import annotations

import re
import unicodedata
from typing import Dict, List

from ..scrapers.base_scraper import JobOffer


REQUIRED_MARKERS = [
    "required",
    "requis",
    "obligatoire",
    "mandatory",
    "must have",
    "must-have",
]


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", normalized).lower().strip()


def calculate_keyword_score(job: JobOffer, profile: Dict) -> float:
    skills = profile.get("skills", {})
    exclusions = profile.get("exclusions", {})
    bonuses = profile.get("bonuses", [])

    description = job.description or ""
    text_to_search = normalize_text(f"{job.title} {description}")

    if _is_excluded(job, exclusions, text_to_search):
        return 0.0

    required = skills.get("required", [])
    if required and not _all_required_present(text_to_search, required):
        return 0.0

    score = 0.0
    max_possible_score = _max_possible_score(skills)

    for category in ["required", "important", "nice_to_have"]:
        for skill in skills.get(category, []):
            keywords = _keywords_from_skill(skill)
            if _contains_any(text_to_search, keywords):
                score += float(skill.get("weight", 0))

    for skill in skills.get("not_known", []):
        keywords = _keywords_from_skill(skill)
        if _contains_any(text_to_search, keywords) and _is_required_in_context(text_to_search, keywords):
            score += float(skill.get("penalty", 0))

    for bonus in bonuses:
        if normalize_text(bonus.get("keyword", "")) in text_to_search:
            score += float(bonus.get("bonus", 0))

    if max_possible_score <= 0:
        return 0.0

    normalized_score = max(0.0, min(100.0, (score / max_possible_score) * 100))
    return round(normalized_score, 1)


def _max_possible_score(skills: Dict) -> float:
    total = 0.0
    for category in ["required", "important", "nice_to_have"]:
        for skill in skills.get(category, []):
            total += float(skill.get("weight", 0))
    return total


def _keywords_from_skill(skill: Dict) -> List[str]:
    keywords = [skill.get("keyword", "")]
    keywords.extend(skill.get("aliases", []) or [])
    return [normalize_text(word) for word in keywords if word]


def _contains_any(text: str, keywords: List[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _all_required_present(text: str, required_skills: List[Dict]) -> bool:
    for skill in required_skills:
        keywords = _keywords_from_skill(skill)
        if not _contains_any(text, keywords):
            return False
    return True


def _is_required_in_context(text: str, keywords: List[str]) -> bool:
    for marker in REQUIRED_MARKERS:
        for keyword in keywords:
            pattern = rf"{re.escape(marker)}.{{0,40}}{re.escape(keyword)}|{re.escape(keyword)}.{{0,40}}{re.escape(marker)}"
            if re.search(pattern, text):
                return True
    return False


def _is_excluded(job: JobOffer, exclusions: Dict, text_to_search: str) -> bool:
    title_exclusions = [normalize_text(value) for value in exclusions.get("titles", [])]
    for exclusion in title_exclusions:
        if exclusion and exclusion in normalize_text(job.title):
            return True

    requirement_exclusions = [normalize_text(value) for value in exclusions.get("requirements", [])]
    for exclusion in requirement_exclusions:
        if exclusion and exclusion in text_to_search:
            return True

    company_exclusions = [normalize_text(value) for value in exclusions.get("companies", [])]
    for exclusion in company_exclusions:
        if exclusion and exclusion in normalize_text(job.company):
            return True

    return False
