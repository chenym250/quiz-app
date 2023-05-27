import dataclasses
import os

from pymongo import ASCENDING
from pymongo import MongoClient

from .access import TopicAccess, QuestionAccess, QuizAccess
from ..access import AccessAPI, Connection


class MongoConnection(Connection):

    def get_access_api(self) -> AccessAPI:
        if os.environ.get('MONGO_URI'):
            client = MongoClient(os.environ['MONGO_URI'])
        else:
            client = MongoClient()
        db = client.quiz_db

        api = AccessAPI()
        api.topic = TopicAccess(db)
        api.question = QuestionAccess(db)
        api.quiz = QuizAccess(db)

        db.questions.create_index([('number', ASCENDING)], unique=True)
        db.questions.create_index([('topic_id', ASCENDING)])

        return api
