from abc import ABC, abstractmethod
from typing import List
from ..models import PatchItem, ValidationScript

class ValidationHandler(ABC):
    kind: str

    @abstractmethod
    def supports(self, item: PatchItem) -> bool: ...

    @abstractmethod
    def build(self, item: PatchItem) -> List[ValidationScript]: ...
