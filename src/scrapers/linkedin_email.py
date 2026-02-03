from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .base_scraper import BaseScraper, JobOffer
from ..utils.deduplication import normalize_url


SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


class LinkedInEmailScraper(BaseScraper):
    def __init__(
        self,
        email_label: str,
        max_emails_per_run: int,
        credentials_path: str,
        token_path: str,
    ) -> None:
        self.email_label = email_label
        self.max_emails_per_run = max_emails_per_run
        self.credentials_path = credentials_path
        self.token_path = token_path
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
        for message_id in messages:
            html = self._get_message_html(service, message_id)
            if not html:
                self._mark_as_read(service, message_id)
                continue

            offers.extend(self._parse_jobs_from_html(html))
            self._mark_as_read(service, message_id)

        return offers

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

    def _mark_as_read(self, service, message_id: str) -> None:
        try:
            service.users().messages().modify(
                userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
        except Exception as exc:
            self.logger.warning("Failed to mark message %s as read: %s", message_id, exc)
