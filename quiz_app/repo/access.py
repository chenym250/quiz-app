from abc import ABC
from typing import Generic, TypeVar

from .. import models


T = TypeVar('T')


class Access(ABC, Generic[T]):
    def list_ids(self) -> list[str]:
        pass

    def get(self, id_: str) -> T:
        pass

    def add(self, m: T) -> T:
        pass

    def update(self, m: T) -> T:
        pass

    def delete(self, id_: str):
        pass


class AccessAPI:
    topic: Access[models.Topic]
    question: Access[models.Question]
    quiz: Access[models.Quiz]
    # record: Access[models.Record]


class Connection(ABC):
    def get_access_api(self) -> AccessAPI:
        pass
