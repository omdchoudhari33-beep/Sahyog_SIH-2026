from abc import ABC, abstractmethod
from typing import Any


class DispatchAdapter(ABC):
    @abstractmethod
    def send(self, *, contact, ticket, correlation_code: str, status_link_url: str) -> dict[str, Any]:
        """Must return {'success': bool, 'raw_response': Any, 'error': str | None}.
        Must never raise - catch all exceptions internally and return success=False."""
        raise NotImplementedError
