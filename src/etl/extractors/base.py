from abc import ABC, abstractmethod

class Extractor(ABC):
    @abstractmethod
    def fetch(self, **kwargs) -> any:
        ...
