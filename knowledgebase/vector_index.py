from abc import ABC, abstractmethod


class VectorIndexRebuilder(ABC):
    @abstractmethod
    def rebuild(self, document_ids):
        raise NotImplementedError


class StubVectorIndexRebuilder(VectorIndexRebuilder):
    def __init__(self):
        self.calls = []

    def rebuild(self, document_ids):
        self.calls.append(list(document_ids))
