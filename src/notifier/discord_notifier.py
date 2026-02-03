from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from ..database.models import Job


class DiscordNotifier:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.enabled = bool(config.get("enabled", False))
        self.webhook_url = config.get("webhook_url")
        self.embed_color = config.get("embed_color", 0x00D166)
        self.logger = logging.getLogger(self.__class__.__name__)

    def send_job(self, job: Job) -> bool:
        if not self.enabled:
            return False
        if not self.webhook_url:
            self.logger.warning("Discord webhook not configured")
            return False

        payload = self._build_payload(job)
        try:
            response = httpx.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code >= 400:
                self.logger.error("Discord webhook error: %s", response.text)
                return False
        except httpx.RequestError as exc:
            self.logger.error("Discord webhook request failed: %s", exc)
            return False
        return True

    def _build_payload(self, job: Job) -> Dict[str, Any]:
        fields = [
            {"name": "Company", "value": job.company or "Unknown", "inline": True},
            {"name": "Location", "value": job.location or "Unknown", "inline": True},
            {"name": "Contract", "value": job.contract_type or "Unknown", "inline": True},
            {"name": "Score", "value": f"{job.final_score}%" if job.final_score is not None else "N/A", "inline": True},
            {"name": "Salary", "value": format_salary(job.salary_min, job.salary_max), "inline": True},
        ]

        if job.ai_reasoning:
            fields.append({"name": "AI Notes", "value": job.ai_reasoning[:200], "inline": False})

        return {
            "embeds": [
                {
                    "title": job.title,
                    "url": job.url,
                    "color": self.embed_color,
                    "fields": fields,
                    "footer": {"text": f"Source: {job.source.upper()}"},
                }
            ]
        }


def format_salary(min_value: Optional[int], max_value: Optional[int]) -> str:
    if min_value and max_value:
        return f"{min_value} - {max_value}"
    if min_value:
        return f">= {min_value}"
    if max_value:
        return f"<= {max_value}"
    return "Not specified"
