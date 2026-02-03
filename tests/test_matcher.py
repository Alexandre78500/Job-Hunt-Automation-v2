from src.matcher.keyword_matcher import calculate_keyword_score
from src.scrapers.base_scraper import JobOffer


def _profile():
    return {
        "skills": {
            "required": [{"keyword": "Power BI", "weight": 10}],
            "important": [{"keyword": "SQL", "weight": 10}],
            "nice_to_have": [],
            "not_known": [],
        },
        "exclusions": {"titles": [], "requirements": [], "companies": []},
        "bonuses": [],
    }


def test_keyword_score_requires_required_skill():
    profile = _profile()
    job = JobOffer(
        source="test",
        external_id=None,
        url="https://example.com/job",
        title="Data Analyst",
        company="Example",
        location=None,
        contract_type=None,
        salary_min=None,
        salary_max=None,
        description="We need SQL and dashboards.",
    )

    assert calculate_keyword_score(job, profile) == 0.0


def test_keyword_score_positive_match():
    profile = _profile()
    job = JobOffer(
        source="test",
        external_id=None,
        url="https://example.com/job",
        title="Power BI Analyst",
        company="Example",
        location=None,
        contract_type=None,
        salary_min=None,
        salary_max=None,
        description="Power BI and SQL required.",
    )

    score = calculate_keyword_score(job, profile)
    assert score > 0
