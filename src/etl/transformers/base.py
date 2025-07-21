from abc import ABC, abstractmethod

class Transformer(ABC):
    @abstractmethod
    def parse(self, raw: any) -> list:
        ...
