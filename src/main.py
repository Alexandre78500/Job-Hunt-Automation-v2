from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import uvicorn

from .api.routes import create_app
from .database.repository import DatabaseManager
from .matcher.keyword_matcher import calculate_keyword_score
from .notifier.discord_notifier import DiscordNotifier
from .scrapers.linkedin_email import LinkedInEmailScraper
from .scrapers.wttj_scraper import WttjScraper
from .utils.config import load_env, load_profile, load_settings, project_root
from .utils.logger import setup_logging


def run_scrape_cycle(settings: dict, profile: dict, repository: DatabaseManager) -> None:
    logger = logging.getLogger("ScrapeCycle")
    scraping = settings.get("scraping", {})

    scrapers = []

    wttj_cfg = scraping.get("wttj", {})
    if wttj_cfg.get("enabled"):
        scrapers.append(
            WttjScraper(
                base_url=wttj_cfg.get("base_url", "https://www.welcometothejungle.com"),
                search_queries=wttj_cfg.get("search_queries", []),
                location=wttj_cfg.get("location"),
                contract_type=wttj_cfg.get("contract_type"),
                max_pages=wttj_cfg.get("max_pages", 5),
                delay_between_requests=wttj_cfg.get("delay_between_requests", 2),
            )
        )

    linkedin_cfg = scraping.get("linkedin", {})
    if linkedin_cfg.get("enabled"):
        credentials_path = Path(
            os.getenv(
                "GMAIL_CREDENTIALS_PATH",
                str(project_root() / "credentials" / "gmail_credentials.json"),
            )
        )
        token_path = Path(
            os.getenv(
                "GMAIL_TOKEN_PATH",
                str(project_root() / "credentials" / "gmail_token.json"),
            )
        )
        scrapers.append(
            LinkedInEmailScraper(
                email_label=linkedin_cfg.get("email_label", "LinkedIn Jobs"),
                max_emails_per_run=linkedin_cfg.get("max_emails_per_run", 50),
                credentials_path=str(credentials_path),
                token_path=str(token_path),
            )
        )

    new_jobs = 0
    for scraper in scrapers:
        if not scraper.is_available():
            logger.warning("Scraper unavailable: %s", scraper.source_name)
            continue
        try:
            offers = scraper.scrape()
        except Exception as exc:
            logger.error("Scraper failed (%s): %s", scraper.source_name, exc)
            continue

        logger.info("Scraper %s returned %s offers", scraper.source_name, len(offers))

        for offer in offers:
            job, created = repository.add_job_offer(offer)
            if not created or job is None:
                continue
            score = calculate_keyword_score(offer, profile)
            repository.update_keyword_score(job.id, score)
            new_jobs += 1

    cleanup_days = settings.get("database", {}).get("cleanup_days", 30)
    repository.cleanup_old_jobs(cleanup_days)
    logger.info("Scraping complete. New jobs: %s", new_jobs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Job Hunter Automation")
    parser.add_argument("--scrape-only", action="store_true", help="Run scraping and exit")
    parser.add_argument("--api-only", action="store_true", help="Run API server only")
    args = parser.parse_args()

    if args.api_only and args.scrape_only:
        parser.error("Choose either --api-only or --scrape-only")

    load_env()
    settings = load_settings()
    profile = load_profile()

    setup_logging(settings.get("app", {}).get("log_level", "INFO"))

    db_path = settings.get("database", {}).get("path", "data/jobs.db")
    db_file = project_root() / db_path
    db_file.parent.mkdir(parents=True, exist_ok=True)

    repository = DatabaseManager(str(db_file))
    repository.init_db()

    if args.api_only:
        notifier = DiscordNotifier(settings.get("notifications", {}).get("discord", {}))
        app = create_app(settings, profile, repository, notifier, scrape_callable=lambda: run_scrape_cycle(settings, profile, repository))
        uvicorn.run(app, host=settings["api"]["host"], port=settings["api"]["port"])
        return

    run_scrape_cycle(settings, profile, repository)


if __name__ == "__main__":
    main()
