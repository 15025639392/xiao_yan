"""Memory service facade.

Public API remains on `MemoryService`, while implementation is split by concern:
- CRUD/search
- extraction
- lifecycle
- prompt-facing aggregation
- personality-aware ranking
"""

from app.memory.associator import MemoryAssociator
from app.memory.extractor import MemoryExtractor
from app.memory.repository import MemoryRepository
from app.memory.service_crud import MemoryCRUDMixin
from app.memory.service_extraction import MemoryExtractionMixin
from app.memory.service_lifecycle import MemoryLifecycleMixin
from app.memory.service_personality import MemoryPersonalityMixin
from app.memory.service_prompt import MemoryPromptMixin
from app.persona.models import PersonalityDimensions


class MemoryService(
    MemoryCRUDMixin,
    MemoryExtractionMixin,
    MemoryLifecycleMixin,
    MemoryPromptMixin,
    MemoryPersonalityMixin,
):
    """Facade over memory subsystem operations."""

    def __init__(
        self,
        repository: MemoryRepository | None = None,
        personality: PersonalityDimensions | None = None,
        llm_gateway=None,
    ) -> None:
        self.repository = repository
        self.personality = personality or PersonalityDimensions()
        self.extractor = MemoryExtractor(
            personality=self.personality,
            llm_gateway=llm_gateway,
        )
        self.associator = MemoryAssociator(repository=repository) if repository else None
