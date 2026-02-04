from __future__ import annotations

import logging
import random
import re
import time
from typing import Callable, Dict, List, Optional, Tuple, TypedDict

import requests
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .base_scraper import BaseScraper, JobOffer
from ..utils.deduplication import normalize_url


SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class JobDetails(TypedDict, total=False):
    description: str
    contract_type: str
    salary_min: Optional[int]
    salary_max: Optional[int]


class LinkedInEmailScraper(BaseScraper):
    def __init__(
        self,
        email_label: str,
        max_emails_per_run: int,
        credentials_path: str,
        token_path: str,
        fetch_details: bool = True,
        delay_between_requests: int = 15,
        max_fetches_per_run: int = 30,
        user_agents: Optional[List[str]] = None,
        li_at_cookie: Optional[str] = None,
        session: Optional[requests.Session] = None,
        cookie_alert_callback: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self.email_label = email_label
        self.max_emails_per_run = max_emails_per_run
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.fetch_details_enabled = fetch_details
        self.delay_between_requests = delay_between_requests
        self.max_fetches_per_run = max_fetches_per_run
        self.user_agents = user_agents or DEFAULT_USER_AGENTS
        self.li_at_cookie = li_at_cookie.strip() if li_at_cookie else None
        self.session = session or requests.Session()
        self.cookie_alert_callback = cookie_alert_callback
        self.cookie_alert_sent = False
        self.cookie_issue_detected = False
        self.last_fetch_count = 0
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    def source_name(self) -> str:
        return "linkedin"

    def is_available(self) -> bool:
        try:
            return bool(self._build_service())
        except Exception:
            return False

    def scrape(self) -> List[JobOffer]:
        self.cookie_issue_detected = False
        self.cookie_alert_sent = False
        self.last_fetch_count = 0
        service = self._build_service()
        if service is None:
            self.logger.warning("Gmail service not available, skipping LinkedIn emails")
            return []

        label_id = self._resolve_label_id(service, self.email_label)
        if label_id is None:
            self.logger.warning("Label '%s' not found, using INBOX", self.email_label)
            label_id = "INBOX"

        messages = self._list_messages(service, label_id)
        if not messages:
            return []

        offers: List[JobOffer] = []
        message_ids_to_mark: List[str] = []
        for message_id in messages:
            html = self._get_message_html(service, message_id)
            if not html:
                self._mark_as_read(service, message_id)
                continue

            offers.extend(self._parse_jobs_from_html(html))
            message_ids_to_mark.append(message_id)

        if not offers:
            return []

        offers = self.fetch_job_details(offers)

        if not self.cookie_issue_detected:
            for message_id in message_ids_to_mark:
                self._mark_as_read(service, message_id)

        return offers

    def fetch_job_details(self, offers: List[JobOffer], max_fetches: Optional[int] = None) -> List[JobOffer]:
        self.last_fetch_count = 0
        if not offers:
            return []
        if not self.fetch_details_enabled:
            return offers
        if not self.li_at_cookie:
            self._mark_offers_failed(offers)
            self._notify_cookie_issue("missing")
            return offers
        limit = self.max_fetches_per_run if max_fetches is None else max_fetches
        if limit <= 0:
            return offers
        return self._fetch_job_details(offers, limit)

    def _build_service(self):
        try:
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        except Exception:
            self.logger.error("Missing Gmail token file: %s", self.token_path)
            return None

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        return build("gmail", "v1", credentials=creds)

    def _resolve_label_id(self, service, label_name: str) -> Optional[str]:
        results = service.users().labels().list(userId="me").execute()
        for label in results.get("labels", []):
            if label.get("name") == label_name:
                return label.get("id")
        return None

    def _list_messages(self, service, label_id: str) -> List[str]:
        results = (
            service.users()
            .messages()
            .list(userId="me", labelIds=[label_id], q="is:unread", maxResults=self.max_emails_per_run)
            .execute()
        )
        return [msg["id"] for msg in results.get("messages", [])]

    def _get_message_html(self, service, message_id: str) -> Optional[str]:
        message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        payload = message.get("payload", {})
        html_part = self._extract_html(payload)
        if html_part:
            return html_part
        return None

    def _extract_html(self, payload: dict) -> Optional[str]:
        mime_type = payload.get("mimeType")
        body = payload.get("body", {})
        data = body.get("data")

        if mime_type == "text/html" and data:
            import base64

            return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="ignore")

        for part in payload.get("parts", []) or []:
            html = self._extract_html(part)
            if html:
                return html
        return None

    def _parse_jobs_from_html(self, html: str) -> List[JobOffer]:
        soup = BeautifulSoup(html, "lxml")
        offers: List[JobOffer] = []
        seen_urls = set()

        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "linkedin.com/jobs/view" not in href:
                continue
            url = self._normalize_href(href)
            if url in seen_urls:
                continue

            title = self._extract_title(link)
            block_text = self._extract_block_text(link)
            company, location = self._extract_company_location(block_text, title)
            description = block_text or title or "LinkedIn job alert"

            if not title:
                title = "LinkedIn Job"
            if not company:
                company = "LinkedIn"

            offers.append(
                JobOffer(
                    source=self.source_name,
                    external_id=None,
                    url=url,
                    title=title,
                    company=company,
                    location=location,
                    contract_type=None,
                    salary_min=None,
                    salary_max=None,
                    description=description,
                    detail_status="pending",
                )
            )
            seen_urls.add(url)

        return offers

    def _normalize_href(self, href: str) -> str:
        if href.startswith("//"):
            href = f"https:{href}"
        elif href.startswith("/"):
            href = f"https://www.linkedin.com{href}"
        elif not href.startswith("http"):
            href = f"https://{href}"
        return normalize_url(href)

    def _extract_title(self, link) -> Optional[str]:
        for attr in ["aria-label", "title"]:
            if link.get(attr):
                return link.get(attr).strip()
        text = link.get_text(" ", strip=True)
        return text if text else None

    def _extract_block_text(self, link) -> str:
        parent = link.parent
        if not parent:
            return ""
        text = " ".join(parent.stripped_strings)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _extract_company_location(self, text: str, title: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        if title and title in text:
            text = text.replace(title, "")
        text = re.sub(r"View job|See job|Voir l'offre", "", text, flags=re.IGNORECASE)
        parts = [part.strip() for part in re.split(r"\u00b7|\||-", text) if part.strip()]
        company = parts[0] if parts else None
        location = parts[1] if len(parts) > 1 else None
        return company, location

    def _fetch_job_details(self, offers: List[JobOffer], max_fetches: int) -> List[JobOffer]:
        updated: List[JobOffer] = []
        fetch_count = 0

        for index, offer in enumerate(offers):
            if fetch_count >= max_fetches:
                offer.detail_status = "pending"
                updated.append(offer)
                continue

            html, status = self._fetch_linkedin_page(offer.url)
            if status == "ok" and html:
                details = self._parse_job_page(html)
                description = details.get("description")
                if description:
                    offer.description = description
                contract_type = details.get("contract_type")
                if contract_type:
                    offer.contract_type = contract_type
                salary_min = details.get("salary_min")
                if salary_min is not None:
                    offer.salary_min = salary_min
                salary_max = details.get("salary_max")
                if salary_max is not None:
                    offer.salary_max = salary_max
                offer.detail_status = "fetched"
            elif status == "auth":
                offer.detail_status = "failed"
                updated.append(offer)
                self._notify_cookie_issue("expired")
                for remaining in offers[index + 1 :]:
                    remaining.detail_status = "failed"
                    updated.append(remaining)
                self.last_fetch_count = fetch_count
                return updated
            elif status == "rate_limited":
                offer.detail_status = "failed"
                updated.append(offer)
                self.logger.warning("LinkedIn rate limited (429). Stopping fetches for this run.")
                for remaining in offers[index + 1 :]:
                    remaining.detail_status = "failed"
                    updated.append(remaining)
                self.last_fetch_count = fetch_count
                return updated
            else:
                offer.detail_status = "failed"

            updated.append(offer)
            fetch_count += 1
            time.sleep(self.delay_between_requests)

        self.last_fetch_count = fetch_count
        return updated

    def _fetch_linkedin_page(self, url: str) -> Tuple[Optional[str], str]:
        if not self.li_at_cookie:
            return None, "auth"
        headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        }

        try:
            response = self.session.get(
                url,
                headers=headers,
                cookies={"li_at": self.li_at_cookie},
                timeout=15,
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            self.logger.warning("LinkedIn fetch failed for %s: %s", url, exc)
            return None, "error"

        if response.status_code == 200:
            if "linkedin.com/login" in response.url or "linkedin.com/signup" in response.url:
                return None, "auth"
            return response.text, "ok"
        if response.status_code in (401, 403):
            return None, "auth"
        if response.status_code == 429:
            return None, "rate_limited"
        if response.status_code == 999:
            self.logger.warning("LinkedIn blocked the request (999) for %s", url)
            return None, "blocked"

        self.logger.warning("LinkedIn fetch returned status %s for %s", response.status_code, url)
        return None, "error"

    def _parse_job_page(self, html: str) -> "JobDetails":
        soup = BeautifulSoup(html, "lxml")

        description = self._extract_description(soup)
        criteria = self._extract_criteria(soup)
        contract_type = criteria.get("contract_type")
        salary_text = criteria.get("salary")
        salary_min, salary_max = self._parse_salary_range(salary_text or "")

        details: JobDetails = {}
        if description:
            details["description"] = description
        if contract_type:
            details["contract_type"] = contract_type
        if salary_min is not None:
            details["salary_min"] = salary_min
        if salary_max is not None:
            details["salary_max"] = salary_max
        return details

    def _extract_description(self, soup: BeautifulSoup) -> str:
        selectors = [
            ("div", {"class": re.compile(r"show-more-less-html__markup")}),
            ("div", {"class": re.compile(r"description__text")}),
            ("div", {"class": re.compile(r"jobs-description-content__text")}),
            ("section", {"id": "job-details"}),
        ]
        for tag, attrs in selectors:
            node = soup.find(tag, attrs=attrs)
            if node:
                text = node.get_text(" ", strip=True)
                if text:
                    return self._clean_text(text)
        return ""

    def _extract_criteria(self, soup: BeautifulSoup) -> Dict[str, str]:
        criteria: Dict[str, str] = {}
        for item in soup.select("li.description__job-criteria-item"):
            label = item.find(["h3", "span"], class_=re.compile(r"description__job-criteria-subheader"))
            value = item.find(["span", "p"], class_=re.compile(r"description__job-criteria-text"))
            if not label or not value:
                continue
            label_text = label.get_text(" ", strip=True).lower()
            value_text = value.get_text(" ", strip=True)
            if ("type" in label_text and "contrat" in label_text) or "employment" in label_text or "emploi" in label_text:
                criteria["contract_type"] = value_text
            if "salary" in label_text or "salaire" in label_text:
                criteria["salary"] = value_text

        return criteria

    def _parse_salary_range(self, text: str) -> Tuple[Optional[int], Optional[int]]:
        if not text:
            return None, None

        numbers: List[int] = []
        for match in re.findall(r"(\d{2,3})\s?[kK]", text):
            numbers.append(int(match) * 1000)

        if not numbers:
            for raw in re.findall(r"\d[\d\s\u00a0]{2,}", text):
                value = int(re.sub(r"\D", "", raw))
                if value >= 1000:
                    numbers.append(value)

        if not numbers:
            return None, None
        if len(numbers) == 1:
            return numbers[0], None
        return min(numbers), max(numbers)

    def _clean_text(self, text: str) -> str:
        return " ".join(text.split())

    def _mark_offers_failed(self, offers: List[JobOffer]) -> None:
        for offer in offers:
            offer.detail_status = "failed"

    def _notify_cookie_issue(self, reason: str) -> None:
        self.cookie_issue_detected = True
        if not self.cookie_alert_callback or self.cookie_alert_sent:
            return

        if reason == "missing":
            message = "Cookie LinkedIn absent. Ajoutez LINKEDIN_LI_AT_COOKIE dans .env pour activer le fetch."
        else:
            message = "Cookie LinkedIn expire. Renouvelez la valeur LINKEDIN_LI_AT_COOKIE dans .env."

        try:
            self.cookie_alert_callback(message)
            self.cookie_alert_sent = True
        except Exception as exc:
            self.logger.warning("Failed to send LinkedIn cookie alert: %s", exc)

    def _mark_as_read(self, service, message_id: str) -> None:
        try:
            service.users().messages().modify(
                userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
        except Exception as exc:
            self.logger.warning("Failed to mark message %s as read: %s", message_id, exc)
