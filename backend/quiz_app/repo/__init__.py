from .access import Connection
from ..repo.mongo.client import MongoConnection


def new_connection() -> Connection:
    return MongoConnection()
