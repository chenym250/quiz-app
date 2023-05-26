import dataclasses
import uuid
from enum import Enum
from datetime import datetime
from typing import ClassVar, Type


ID_TBD = 'TBD'


class QuestionType(Enum):
    MULTI_CHOICE = '单项选择题'
    MULTI_ANSWER = '多项选择题'
    SHORT_ANSWER = '简答题'
    UNDEFINED = '\x00'*10

    @classmethod
    def from_val(cls, val: str) -> 'QuestionType':
        for qt in cls:
            if qt.value == val:
                return qt
        raise ValueError

    def register(self, clazz: Type['Question']):
        self.__qmodel__ = clazz
        clazz.__of_type__ = self
        return clazz

    def new_question(self, id_: str, text: str) -> 'Question':
        try:
            return self.__qmodel__(id_, text)
        except AttributeError:
            raise RuntimeError('not registered')


@dataclasses.dataclass
class Choice:
    letter: str
    text: str

    def __str__(self):
        return f'{self.letter}. {self.text}'


@dataclasses.dataclass
class _Question:
    number: str
    text: str
    topic_id: str | None = None
    revision: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    of_type: QuestionType = QuestionType.UNDEFINED

    __of_type__: ClassVar[QuestionType] = QuestionType.UNDEFINED

    def __post_init__(self):
        self.of_type = self.__of_type__

    def question_type(self) -> QuestionType:
        try:
            return self.of_type
        except AttributeError:
            raise RuntimeError('not registered')


@QuestionType.MULTI_CHOICE.register
@dataclasses.dataclass
class MultiChoice(_Question):
    choices: list[Choice] = dataclasses.field(default_factory=list)
    answer: str | None = None
    explain: str | None = None

    def is_correct(self, answers: list[str]) -> bool:
        if len(answers) == 1 and any(answers[0] == c.letter for c in self.choices):
            return answers[0] == self.answer
        raise ValueError


@QuestionType.MULTI_ANSWER.register
@dataclasses.dataclass
class MultiAnswer(_Question):
    choices: list[Choice] = dataclasses.field(default_factory=list)
    answer: tuple[str] | None = None
    explain: str | None = None

    def is_correct(self, answers: list[str]) -> bool:
        choices = {c.letter for c in self.choices}
        answers = set(answers)
        if any(a not in choices for a in answers):
            raise ValueError
        return answers == set(self.answer)


@QuestionType.SHORT_ANSWER.register
@dataclasses.dataclass
class ShortAnswer(_Question):
    explain: str | None = None

    def is_correct(self, answers: list[str]) -> bool:
        return True


Question = MultiChoice | MultiAnswer | ShortAnswer


@dataclasses.dataclass
class Topic:
    topic_id: str
    name: str
    questions: list[Question] = dataclasses.field(default_factory=list, repr=False)


class ProblemAnswerStatus(str, Enum):
    NOT_ANSWERED = 'NOT_ANSWERED'
    CORRECT = 'CORRECT'
    INCORRECT = 'INCORRECT'


@dataclasses.dataclass
class QuizProblem:
    question: Question
    status: 'ProblemAnswerStatus' = ProblemAnswerStatus.NOT_ANSWERED
    user_answer: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Quiz:
    id_: str
    name: str
    topics: list[str]
    create_time: datetime
    update_time: datetime | None = None
    begin_time: datetime | None = None
    done_time: datetime | None = None
    problems: list[QuizProblem] = dataclasses.field(default_factory=list, repr=False)

    @property
    def size(self) -> int:
        return len(self.problems)

    @property
    def current_index(self) -> int:
        for i, problem in enumerate(self.problems):
            if problem.status == ProblemAnswerStatus.NOT_ANSWERED:
                return i
        return -1

    @property
    def is_done(self) -> bool:
        return self.current_index == -1
