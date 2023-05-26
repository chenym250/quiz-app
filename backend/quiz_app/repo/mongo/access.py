import typing

if typing.TYPE_CHECKING:
    from pymongo.collection import Collection
    from pymongo.database import Database
    from pymongo.command_cursor import CommandCursor

from .serialization import serialize, deserialize
from .. import access
from ...models import *


class TopicAccess(access.Access[Topic]):

    db: 'Database'

    def __init__(self, db: 'Database'):
        self.db = db

    @property
    def topics(self) -> 'Collection':
        return self.db.topics

    @property
    def questions(self) -> 'Collection':
        return self.db.questions

    def list_ids(self) -> list[str]:
        return [
            topic['topic_id']
            for topic in self.topics.find(projection=['topic_id'])
        ]

    def get(self, id_: str) -> Topic:
        cursor: 'CommandCursor' = self.topics.aggregate(pipeline=[
            {
                '$match': {
                    'topic_id': id_
                }
            },
            {
                '$lookup': {
                    'from': 'questions',
                    'localField': 'topic_id',
                    'foreignField': 'topic_id',
                    'as': 'questions',
                }
            }
        ])
        return deserialize(Topic, cursor.next())

    def add(self, m: Topic) -> Topic:
        questions = m.questions
        raw = serialize(m)
        _id = self.topics.insert_one(raw).inserted_id
        raw = self.topics.find_one({'_id': _id})

        m = deserialize(Topic, raw)
        for q in questions:
            raw = serialize(q)
            _id = self.questions.insert_one(raw).inserted_id
            raw = self.questions.find_one({'_id': _id})
            m.questions.append(deserialize(Question, raw))
        return m

    def update(self, m: Topic) -> Topic:
        raw = serialize(m)
        raw = self.topics.find_one_and_replace({'topic_id': m.topic_id}, raw)
        return deserialize(Topic, raw)

    def delete(self, id_: str):
        self.topics.delete_many({'topic_id': id_})
        # cascade delete
        self.questions.delete_many({'topic_id': id_})


class QuestionAccess(access.Access[Question]):

    db: 'Database'

    def __init__(self, db: 'Database'):
        self.db = db

    @property
    def questions(self) -> 'Collection':
        return self.db.questions

    def list_ids(self) -> list[str]:
        return [
            topic['number']
            for topic in self.questions.find(projection=['number'])
        ]

    def get(self, id_: str) -> Question:
        raw = self.questions.find_one({'number': id_})
        return deserialize(Question, raw)

    def add(self, m: Question) -> Question:
        raw = serialize(m)
        _id = self.questions.insert_one(raw).inserted_id
        raw = self.questions.find_one({'_id': _id})
        return deserialize(Question, raw)

    def update(self, m: Question) -> Question:
        raw = serialize(m)
        raw = self.questions.find_one_and_replace({'number': m.number}, raw)
        return deserialize(Question, raw)

    def delete(self, id_: str):
        self.questions.delete_many({'number': id_})
