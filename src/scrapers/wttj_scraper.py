from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, JobOffer


class WttjScraper(BaseScraper):
    def __init__(
        self,
        base_url: str,
        search_queries: List[str],
        location: Optional[str],
        contract_type: Optional[str],
        max_pages: int = 5,
        delay_between_requests: int = 2,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.search_queries = search_queries
        self.location = location
        self.contract_type = contract_type
        self.max_pages = max_pages
        self.delay_between_requests = delay_between_requests
        self.session = session or requests.Session()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._algolia_config: Optional[Dict[str, str]] = None
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (JobHunterAutomation/1.0; +https://example.com)"
            }
        )

    @property
    def source_name(self) -> str:
        return "wttj"

    def is_available(self) -> bool:
        try:
            response = self.session.get(f"{self.base_url}/en/jobs", timeout=10)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def scrape(self) -> List[JobOffer]:
        if not self._ensure_algolia_config():
            self.logger.warning("Algolia config unavailable, skipping WTTJ scraping")
            return []

        offers: List[JobOffer] = []
        for query in self.search_queries:
            offers.extend(self._scrape_query(query))
        return offers

    def _scrape_query(self, query: str) -> List[JobOffer]:
        offers: List[JobOffer] = []
        page = 0
        while page < self.max_pages:
            payload = self._algolia_search(query, page)
            hits = payload.get("hits", [])
            if not hits:
                break

            for hit in hits:
                job = self._hit_to_job(hit)
                if not job:
                    continue
                if self._should_skip(job):
                    continue
                offers.append(job)

            nb_pages = payload.get("nbPages", 0)
            if nb_pages and page >= nb_pages - 1:
                break

            page += 1
            time.sleep(self.delay_between_requests)

        return offers

    def _ensure_algolia_config(self) -> bool:
        if self._algolia_config:
            return True

        try:
            response = self.session.get(f"{self.base_url}/en/jobs", timeout=15)
            response.raise_for_status()
        except requests.RequestException as exc:
            self.logger.error("Failed to load WTTJ page: %s", exc)
            return False

        text = response.text
        app_id = self._extract_env_value(text, "ALGOLIA_APPLICATION_ID")
        api_key = self._extract_env_value(text, "ALGOLIA_API_KEY_CLIENT")
        index_prefix = self._extract_env_value(text, "ALGOLIA_JOBS_INDEX_PREFIX")

        if not app_id or not api_key or not index_prefix:
            self.logger.error("Could not find Algolia config in WTTJ page")
            return False

        self._algolia_config = {
            "app_id": app_id,
            "api_key": api_key,
            "index": index_prefix,
        }
        return True

    def _extract_env_value(self, text: str, key: str) -> Optional[str]:
        pattern = rf'"{re.escape(key)}":"(.*?)"'
        match = re.search(pattern, text)
        return match.group(1) if match else None

    def _algolia_search(self, query: str, page: int) -> Dict[str, Any]:
        assert self._algolia_config is not None
        app_id = self._algolia_config["app_id"]
        api_key = self._algolia_config["api_key"]
        index = self._algolia_config["index"]

        url = f"https://{app_id}-dsn.algolia.net/1/indexes/{index}/query"
        headers = {
            "X-Algolia-Application-Id": app_id,
            "X-Algolia-API-Key": api_key,
            "Content-Type": "application/json",
        }
        body = {
            "query": query,
            "page": page,
            "hitsPerPage": 20,
            "attributesToRetrieve": ["*"],
            "attributesToHighlight": [],
        }

        try:
            response = self.session.post(url, headers=headers, data=json.dumps(body), timeout=20)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            self.logger.error("Algolia search failed: %s", exc)
            return {}

    def _hit_to_job(self, hit: Dict[str, Any]) -> Optional[JobOffer]:
        title = self._first_value(hit, ["title", "name", "job_title"])
        company = self._first_value(hit, ["company_name", "organization_name", "company", "organization"])
        if isinstance(company, dict):
            company = company.get("name")

        if not title or not company:
            return None

        url = self._first_value(hit, ["public_url", "url", "apply_url"])
        if url and url.startswith("/"):
            url = f"{self.base_url}{url}"

        office = hit.get("office") or {}
        location_parts = []
        if isinstance(office, dict):
            city = office.get("city")
            country = office.get("country")
            if city:
                location_parts.append(city)
            if country:
                location_parts.append(country)
        location = ", ".join(location_parts) if location_parts else hit.get("location")

        contract_type = self._first_value(hit, ["contract_type", "contract_type_name", "contract"])
        if isinstance(contract_type, list):
            contract_type = ", ".join([str(item) for item in contract_type])

        description = self._first_value(hit, ["description", "mission", "profile", "summary", "description_text"]) or ""
        if isinstance(description, dict):
            description = " ".join(str(value) for value in description.values())
        elif not isinstance(description, str):
            description = str(description)
        description = self._clean_text(description)

        salary_min = self._safe_int(hit.get("salary_min"))
        salary_max = self._safe_int(hit.get("salary_max"))

        external_id = self._first_value(hit, ["id", "objectID"])

        if not url:
            return None

        return JobOffer(
            source=self.source_name,
            external_id=str(external_id) if external_id is not None else None,
            url=url,
            title=str(title),
            company=str(company),
            location=str(location) if location else None,
            contract_type=str(contract_type) if contract_type else None,
            salary_min=salary_min,
            salary_max=salary_max,
            description=description,
        )

    def _first_value(self, data: Dict[str, Any], keys: List[str]) -> Optional[Any]:
        for key in keys:
            if key in data and data[key] not in (None, ""):
                return data[key]
        return None

    def _safe_int(self, value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _clean_text(self, text: str) -> str:
        if "<" in text and ">" in text:
            soup = BeautifulSoup(text, "lxml")
            text = soup.get_text(" ")
        return " ".join(text.split())

    def _should_skip(self, job: JobOffer) -> bool:
        if self.contract_type and job.contract_type:
            if not self._match_contract(job.contract_type, self.contract_type):
                return True
        if self.location and job.location:
            if not self._match_location(job.location, self.location):
                return True
        return False

    def _match_contract(self, job_contract: str, desired: str) -> bool:
        job_contract_norm = self._normalize(job_contract)
        desired_norm = self._normalize(desired)
        if desired_norm in job_contract_norm:
            return True
        if desired_norm == "cdi" and any(token in job_contract_norm for token in ["permanent", "full_time"]):
            return True
        return False

    def _match_location(self, job_location: str, desired: str) -> bool:
        job_location_norm = self._normalize(job_location)
        tokens = [token for token in re.split(r"[\s,/]+", self._normalize(desired)) if token]
        return any(token in job_location_norm for token in tokens)

    def _normalize(self, text: str) -> str:
        import unicodedata

        normalized = unicodedata.normalize("NFKD", text)
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return normalized.lower()
