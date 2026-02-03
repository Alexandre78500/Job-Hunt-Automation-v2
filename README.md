# Job Hunter Automation

Daily job scraping and scoring pipeline with OpenClaw integration.

## Features
- Scrape job offers from Welcome to the Jungle (WTTJ)
- Parse LinkedIn job alert emails via Gmail API
- Keyword-based prefilter scoring
- OpenClaw-ready API for AI scoring
- Discord webhook notifications
- SQLite storage with deduplication

## Quick start
1. Create a virtual environment
2. Install dependencies
3. Configure environment variables
4. Configure Gmail OAuth
5. Run scraping or API

```bash
python -m venv .venv
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set your values.

Create a Gmail label for LinkedIn job alerts (default: `LinkedIn Jobs`).

```bash
python scripts/setup_gmail_oauth.py
```

```bash
python -m src.main --scrape-only
python -m src.main --api-only
```

## OpenClaw API
- `GET /api/jobs/pending`
- `POST /api/jobs/scores`
- `GET /api/stats`
- `POST /api/trigger-scrape`

## Notes
- LinkedIn scraping is done via Gmail job alert emails.
- Configure Gmail label in `config/settings.yaml`.
- The WTTJ scraper uses Algolia search API discovered from their public page.
