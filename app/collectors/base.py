from abc import ABC, abstractmethod
from typing import Any


class BaseCollector(ABC):
    """
    Base interface for all data collectors.

    Each collector should implement the collect()
    method and return normalized records.
    """

    platform: str

    @abstractmethod
    async def collect(
        self,
        keyword: str,
        max_results: int = 25,
    ) -> list[dict[str, Any]]:
        """
        Collect records for a given keyword.
        """
        raise NotImplementedError