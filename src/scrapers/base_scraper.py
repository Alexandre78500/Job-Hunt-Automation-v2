from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class JobOffer:
    source: str
    external_id: Optional[str]
    url: str
    title: str
    company: str
    location: Optional[str]
    contract_type: Optional[str]
    salary_min: Optional[int]
    salary_max: Optional[int]
    description: str
    detail_status: Optional[str] = None
    scraped_at: datetime = field(default_factory=datetime.utcnow)


class BaseScraper(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def scrape(self) -> List[JobOffer]:
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError
