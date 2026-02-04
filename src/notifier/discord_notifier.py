from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import httpx

from ..database.models import Job


class DiscordNotifier:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.enabled = bool(config.get("enabled", False))
        self.webhook_url = config.get("webhook_url")
        self.embed_color = config.get("embed_color", 0x00D166)
        self.logger = logging.getLogger(self.__class__.__name__)

    def send_job(self, job: Job) -> bool:
        payload = self._build_payload(job)
        return self._send_payload(payload)

    def send_message(self, content: str) -> bool:
        payload = {"content": content}
        return self._send_payload(payload)

    def send_daily_recap(self, jobs_by_source: Dict[str, List[Job]]) -> bool:
        if not jobs_by_source:
            return False

        total = sum(len(jobs) for jobs in jobs_by_source.values())
        summary_parts = [f"{len(jobs)} {source.upper()}" for source, jobs in jobs_by_source.items() if jobs]
        summary = ", ".join(summary_parts) if summary_parts else "0"

        embeds: List[Dict[str, Any]] = [
            {
                "title": f"Job Hunter - Rapport du {date.today().strftime('%d/%m/%Y')}",
                "description": f"**{total} offres** ({summary})",
                "color": self.embed_color,
            }
        ]

        for source, jobs in jobs_by_source.items():
            if not jobs:
                continue

            source_label = {"wttj": "Welcome to the Jungle", "linkedin": "LinkedIn"}.get(source, source)
            source_color = 0xFFCD00 if source == "wttj" else 0x5865F2 if source == "linkedin" else self.embed_color
            lines = []

            sorted_jobs = sorted(jobs, key=lambda job: job.final_score or 0, reverse=True)
            for index, job in enumerate(sorted_jobs, 1):
                score_str = f"**{job.final_score}%**" if job.final_score is not None else "N/A"
                location_str = f" | {job.location}" if job.location else ""
                contract_str = f" | {job.contract_type}" if job.contract_type else ""
                reasoning = f"\n> {job.ai_reasoning[:150]}" if job.ai_reasoning else ""
                lines.append(
                    f"**{index}. [{job.title}]({job.url})** — {job.company}\n"
                    f"Score: {score_str}{location_str}{contract_str}{reasoning}\n"
                )

            description = "\n".join(lines)
            if len(description) > 4000:
                description = f"{description[:3990]}..."

            embeds.append(
                {
                    "title": f"── {source_label} ({len(jobs)} offres) ──",
                    "description": description,
                    "color": source_color,
                }
            )

        payload = {"embeds": embeds[:10]}
        return self._send_payload(payload)

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

    def _send_payload(self, payload: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        if not self.webhook_url:
            self.logger.warning("Discord webhook not configured")
            return False

        try:
            response = httpx.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code >= 400:
                self.logger.error("Discord webhook error: %s", response.text)
                return False
        except httpx.RequestError as exc:
            self.logger.error("Discord webhook request failed: %s", exc)
            return False
        return True


def format_salary(min_value: Optional[int], max_value: Optional[int]) -> str:
    if min_value and max_value:
        return f"{min_value} - {max_value}"
    if min_value:
        return f">= {min_value}"
    if max_value:
        return f"<= {max_value}"
    return "Not specified"
