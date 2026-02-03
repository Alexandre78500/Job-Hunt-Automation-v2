from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterator, List, Optional, Tuple

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Job
from ..scrapers.base_scraper import JobOffer
from ..utils.deduplication import generate_job_hash


class DatabaseManager:
    def __init__(self, db_path: str) -> None:
        path = Path(db_path).resolve()
        self.engine = create_engine(f"sqlite:///{path.as_posix()}", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def init_db(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def add_job_offer(self, offer: JobOffer) -> Tuple[Optional[Job], bool]:
        job_hash = generate_job_hash(offer.url, offer.title, offer.company)
        with self.session_scope() as session:
            job = Job(
                hash=job_hash,
                source=offer.source,
                external_id=offer.external_id,
                url=offer.url,
                title=offer.title,
                company=offer.company,
                location=offer.location,
                contract_type=offer.contract_type,
                salary_min=offer.salary_min,
                salary_max=offer.salary_max,
                description=offer.description,
                scraped_at=offer.scraped_at,
            )
            session.add(job)
            try:
                session.flush()
                return job, True
            except IntegrityError:
                session.rollback()
                existing = session.execute(select(Job).where(Job.hash == job_hash)).scalar_one_or_none()
                return existing, False

    def update_keyword_score(self, job_id: int, score: float) -> None:
        with self.session_scope() as session:
            job = session.get(Job, job_id)
            if job:
                job.keyword_score = score

    def get_pending_jobs(self, keyword_threshold: float, limit: int = 50) -> List[Job]:
        with self.session_scope() as session:
            stmt = (
                select(Job)
                .where(Job.status == "new")
                .where(Job.keyword_score.is_not(None))
                .where(Job.keyword_score >= keyword_threshold)
                .order_by(Job.keyword_score.desc())
                .limit(limit)
            )
            return list(session.execute(stmt).scalars())

    def update_ai_scores(self, scores: List[dict], weights: dict) -> List[Job]:
        updated_jobs: List[Job] = []
        with self.session_scope() as session:
            for item in scores:
                job = session.get(Job, item["job_id"])
                if not job:
                    continue
                ai_score = float(item["ai_score"])
                job.ai_score = ai_score
                job.ai_reasoning = item.get("reasoning")
                keyword_score = job.keyword_score or 0.0
                job.final_score = round(
                    (weights.get("keyword_score", 0.0) * keyword_score)
                    + (weights.get("ai_score", 1.0) * ai_score),
                    2,
                )
                job.status = "scored"
                job.scored_at = datetime.utcnow()
                updated_jobs.append(job)
        return updated_jobs

    def mark_notified(self, job_id: int) -> None:
        with self.session_scope() as session:
            job = session.get(Job, job_id)
            if job:
                job.status = "notified"
                job.notified_at = datetime.utcnow()

    def cleanup_old_jobs(self, days: int) -> int:
        cutoff = datetime.utcnow() - timedelta(days=days)
        with self.session_scope() as session:
            jobs = session.execute(select(Job).where(Job.scraped_at < cutoff)).scalars().all()
            deleted = len(jobs)
            for job in jobs:
                session.delete(job)
        return deleted

    def get_stats(self) -> dict:
        with self.session_scope() as session:
            total = session.query(Job).count()
            new = session.query(Job).filter(Job.status == "new").count()
            scored = session.query(Job).filter(Job.status == "scored").count()
            notified = session.query(Job).filter(Job.status == "notified").count()
        return {
            "total": total,
            "new": new,
            "scored": scored,
            "notified": notified,
        }
