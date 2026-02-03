from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ..matcher.ai_scorer import build_scoring_prompt


class JobForScoring(BaseModel):
    id: int
    title: str
    company: str
    location: Optional[str] = None
    contract_type: Optional[str] = None
    description: str
    keyword_score: float
    url: str
    prompt: Optional[str] = None


class ScoreSubmission(BaseModel):
    job_id: int
    ai_score: float = Field(ge=0, le=100)
    reasoning: str


class BulkScoreSubmission(BaseModel):
    scores: List[ScoreSubmission]


def create_app(settings: dict, profile: dict, repository, notifier, scrape_callable=None) -> FastAPI:
    app = FastAPI(title="Job Hunter API", version="1.0.0")
    app.state.settings = settings
    app.state.profile = profile
    app.state.repository = repository
    app.state.notifier = notifier
    app.state.scrape_callable = scrape_callable

    @app.get("/api/jobs/pending", response_model=List[JobForScoring])
    def get_pending_jobs(limit: int = 50, include_prompt: bool = False):
        threshold = app.state.settings["scoring"]["keyword_prefilter_threshold"]
        jobs = app.state.repository.get_pending_jobs(threshold, limit=limit)
        results: List[JobForScoring] = []
        for job in jobs:
            prompt = build_scoring_prompt(job, app.state.profile) if include_prompt else None
            results.append(
                JobForScoring(
                    id=job.id,
                    title=job.title,
                    company=job.company,
                    location=job.location,
                    contract_type=job.contract_type,
                    description=job.description or "",
                    keyword_score=job.keyword_score or 0.0,
                    url=job.url,
                    prompt=prompt,
                )
            )
        return results

    @app.post("/api/jobs/scores")
    def submit_scores(submission: BulkScoreSubmission):
        weights = app.state.settings["scoring"]["weights"]
        updated_jobs = app.state.repository.update_ai_scores(
            [score.model_dump() for score in submission.scores], weights
        )
        threshold = app.state.settings["scoring"]["ai_scoring_threshold"]
        for job in updated_jobs:
            if job.final_score is not None and job.final_score >= threshold:
                if app.state.notifier.send_job(job):
                    app.state.repository.mark_notified(job.id)
        return {"updated": len(updated_jobs)}

    @app.get("/api/stats")
    def get_stats():
        return app.state.repository.get_stats()

    @app.post("/api/trigger-scrape")
    def trigger_scrape():
        if not app.state.scrape_callable:
            raise HTTPException(status_code=503, detail="Scrape trigger not configured")
        app.state.scrape_callable()
        return {"status": "started"}

    return app
