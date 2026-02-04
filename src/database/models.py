from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hash = Column(String, unique=True, nullable=False)

    source = Column(String, nullable=False)
    external_id = Column(String)
    url = Column(String, nullable=False)

    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String)
    contract_type = Column(String)
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    description = Column(Text)

    keyword_score = Column(Float)
    ai_score = Column(Float)
    final_score = Column(Float)
    ai_reasoning = Column(Text)

    status = Column(String, default="new")
    detail_status = Column(String, default="pending")
    scraped_at = Column(DateTime, server_default=func.now())
    scored_at = Column(DateTime)
    notified_at = Column(DateTime)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    completed_at = Column(DateTime)
    jobs_found = Column(Integer, default=0)
    jobs_new = Column(Integer, default=0)
    jobs_duplicate = Column(Integer, default=0)
    error_message = Column(Text)
    status = Column(String, default="running")
