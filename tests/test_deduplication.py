from src.utils.deduplication import generate_job_hash


def test_generate_job_hash_normalizes_tracking_params():
    url_a = "https://example.com/jobs/123?utm_source=test&utm_campaign=demo"
    url_b = "https://example.com/jobs/123"
    assert generate_job_hash(url_a) == generate_job_hash(url_b)
