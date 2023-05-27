import dataclasses
import json
import string
from enum import Enum
from typing import Any, Callable, Type, TypeVar

from ...models import Question, Topic, Quiz, QuizProblem
from ...models import QuestionType, ProblemAnswerStatus

T = TypeVar('T')


class Serializer:
    __custom__: dict[Type, Callable[[Any], dict]] = None

    def serialize(self, obj: T) -> dict | list[dict] | str:
        for cls, func in (self.__custom__ or {}).items():
            if isinstance(obj, cls):
                return func(obj)

        # default impl
        try:
            j = json.dumps(obj)
            return json.loads(j)
        except TypeError:
            pass
        if isinstance(obj, dict):
            return {k: serialize(v) for k, v in obj}
        if isinstance(obj, (list, tuple, set)):
            return [serialize(v) for v in obj]
        if isinstance(obj, Enum):
            return obj.name
        if not dataclasses.is_dataclass(obj):
            return str(obj)

        result = {}
        for field in dataclasses.fields(obj):
            field: dataclasses.Field
            value = getattr(obj, field.name)
            result[field.name] = serialize(value)
        return result

    def register(self, *classes: Type[T]):
        if self.__custom__ is None:
            self.__custom__ = {}

        def wrapper(func: Callable[[Any], dict]) -> Callable[[Any], dict]:
            for cls in classes:
                self.__custom__[cls] = func
            return func
        return wrapper


class Deserializer:
    __custom__: dict[Type, Callable[[Type, dict], Any]] = None

    def deserialize(self, cls: Type[T], src: dict) -> T:
        # src = remove_camel(src)
        if cls in (self.__custom__ or {}):
            return self.__custom__[cls](cls, src)
        raise RuntimeError

    def register(self, *classes: Type[T]):
        if self.__custom__ is None:
            self.__custom__ = {}

        def wrapper(func: Callable[[Type, dict], Any]) -> Callable[[Type, dict], Any]:
            for cls in classes:
                self.__custom__[cls] = func
            return func
        return wrapper


_serializer = Serializer()
_deserializer = Deserializer()

serialize = _serializer.serialize
deserialize = _deserializer.deserialize


@_serializer.register(Enum)
def _serialize_enum(e):
    return e.name


@_serializer.register(Topic)
def _serialize_topic(t):
    return {
        'topic_id': t.topic_id,
        'name': t.name,
    }


@_deserializer.register(Topic)
def _deserialize_topic(cls: Type[Topic], dict_: dict) -> Topic:
    dict_ = dict(dict_)
    if 'questions' in dict_:
        dict_['questions'] = [_deserialize_question(Question, q) for q in dict_['questions']]
    del dict_['_id']
    return Topic(**dict_)


@_deserializer.register(Question)
def _deserialize_question(cls: Type[Question], dict_: dict) -> Question:
    dict_ = dict(dict_)
    if 'of_type' not in dict_:
        raise ValueError
    question_type = QuestionType[dict_['of_type']]
    if '_id' in dict_:
        del dict_['_id']
    return question_type.__qmodel__(**dict_)


@_deserializer.register(Quiz)
def _deserialize_quiz(cls: Type[Quiz], dict_: dict) -> Quiz:
    dict_ = dict(dict_)
    if 'problems' in dict_:
        dict_['problems'] = [_deserialize_quiz_problem(QuizProblem, q) for q in dict_['problems']]
    del dict_['_id']
    return Quiz(**dict_)


@_deserializer.register(QuizProblem)
def _deserialize_quiz_problem(cls: Type[QuizProblem], dict_: dict) -> QuizProblem:
    return QuizProblem(
        question=_deserialize_question(Question, dict_['question']),
        status=ProblemAnswerStatus[dict_['status']],
        user_answer=dict_.get('user_answer', []),
    )


def _process_dict(d: dict, key_func=lambda x: x, value_func=lambda x: x):
    if not isinstance(d, dict):
        return d

    new = {}
    for k, v in d.items():
        k = key_func(k)
        if isinstance(v, dict):
            v = _process_dict(v)
        elif isinstance(v, list):
            v = [_process_dict(v2) for v2 in v]
        else:
            v = value_func(v)
        new[k] = v
    return new


def _camel_to_snake(s: str) -> str:
    for letter, repl in alphabet.items():
        if letter in s:
            s = s.replace(letter, repl)
    return s


alphabet = {
    letter: '_' + letter.lower()
    for letter in string.ascii_uppercase
}


def remove_camel(d: dict) -> dict:
    return _process_dict(d, key_func=_camel_to_snake)
