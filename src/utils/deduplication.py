from __future__ import annotations

import hashlib
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "ref",
    "source",
}


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    essential_params = {key: value for key, value in params.items() if key not in TRACKING_PARAMS}
    cleaned = parsed._replace(query=urlencode(essential_params, doseq=True))
    return urlunparse(cleaned)


def generate_job_hash(url: str, title: Optional[str] = None, company: Optional[str] = None) -> str:
    if url and url.startswith("http"):
        content = normalize_url(url)
    elif title and company:
        content = f"{title.strip().lower()}|{company.strip().lower()}"
    else:
        raise ValueError("Cannot generate hash: url or title+company required")

    return hashlib.sha256(content.encode("utf-8")).hexdigest()
