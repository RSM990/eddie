from abc import ABC, abstractmethod

class Loader(ABC):
    @abstractmethod
    def load(self, items: list) -> None:
        ...
