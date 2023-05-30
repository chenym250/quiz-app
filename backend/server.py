import random
import uuid
from datetime import timedelta

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from quiz_app.repo.access import AccessAPI
from quiz_app.repo import new_connection
from quiz_app.models import *


app = FastAPI()
repo: AccessAPI = new_connection().get_access_api()

origins = [
    "http://localhost",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class NewQuizParam(BaseModel):
    topics: list[str]
    shuffle: bool
    total_question: int | None = None
    duration: timedelta | None = None
    name: str | None = None


class QuizDisplay(BaseModel):
    quiz_id: str
    name: str
    topic_ids: list[str]

    size: int
    current_index: int
    is_done: bool

    create_time: datetime
    update_time: datetime | None = None
    begin_time: datetime | None = None
    done_time: datetime | None = None

    @classmethod
    def from_model(cls, quiz: Quiz) -> 'QuizDisplay':
        index = quiz.current_index
        return QuizDisplay(
            quiz_id=quiz.quiz_id,
            name=quiz.name,
            topic_ids=quiz.topic_ids,
            size=quiz.size,
            is_done=quiz.is_done,
            current_index=index,
            create_time=quiz.create_time,
            update_time=quiz.update_time,
            begin_time=quiz.begin_time,
            done_time=quiz.done_time,
        )


@app.get('/topic/{topic_id}')
def get_topic(topic_id: str) -> Topic:
    return repo.topic.get(topic_id)


@app.get('/question/{number}')
def get_question(number: str) -> Question:
    return repo.question.get(number)


@app.put('/quiz')
def new_quiz(param: NewQuizParam) -> QuizDisplay:
    # find questions of topics
    if 'all' in param.topics:
        param.topics = repo.topic.list_ids()

    questions = []
    for topic_id in param.topics:
        questions.extend(repo.topic.get(topic_id).questions)

    # de-dup
    questions = list({q.number: q for q in questions}.values())
    # shrink
    if param.total_question is not None:
        random.shuffle(questions)
        questions = questions[:param.total_question]
    # sort
    if not param.shuffle:
        questions.sort(key=lambda q: q.number)

    id_ = str(uuid.uuid4())
    now = datetime.now()

    quiz = Quiz(
        quiz_id=id_,
        name=(param.name if param.name else f'quiz:{id_}'),
        topic_ids=sorted({q.topic_id for q in questions}),
        problems=[QuizProblem(q) for q in questions],
        create_time=now,
    )

    quiz = repo.quiz.add(quiz)
    return QuizDisplay.from_model(quiz)


@app.get('/quiz/{quiz_id}')
def get_quiz(quiz_id: str) -> QuizDisplay:
    return QuizDisplay.from_model(repo.quiz.get(quiz_id))


@app.get('/quiz/{quiz_id}/{question_index}')
def get_quiz_question(quiz_id: str, question_index: int) -> QuizProblem:
    quiz = repo.quiz.get(quiz_id)
    try:
        problem = quiz.problems[question_index]
    except IndexError:
        raise HTTPException(status_code=404, detail='question not found')
    if problem.status == ProblemAnswerStatus.NOT_ANSWERED:
        problem.question.answer = None
        problem.question.explain = None
    return problem


@app.post('/quiz/{quiz_id}/{question_index}')
def submit_quiz_question(quiz_id: str, question_index: int, answers: list[str]) -> QuizProblem:
    quiz = repo.quiz.get(quiz_id)

    try:
        problem = quiz.problems[question_index]
    except IndexError:
        raise HTTPException(status_code=404, detail='question not found')

    if problem.status != ProblemAnswerStatus.NOT_ANSWERED:
        raise HTTPException(status_code=400, detail='question already answered')
    problem.user_answer = answers
    try:
        is_correct = problem.question.is_correct(answers)
    except ValueError:
        raise HTTPException(status_code=400, detail='answer not acceptable')

    if is_correct:
        problem.status = ProblemAnswerStatus.CORRECT
    else:
        problem.status = ProblemAnswerStatus.INCORRECT
        update_all_wrong_answer_quiz(problem.question)

    repo.quiz.update(quiz)
    return problem


def update_all_wrong_answer_quiz(question: Question):
    quiz_id = 'all_wrong'
    quiz = repo.quiz.get(quiz_id)

    # de-dup
    # for this version of Python all dicts are ordered, so orders are reserved.
    question_map = {}
    for i, q in enumerate(quiz.problems):
        if q.status == ProblemAnswerStatus.NOT_ANSWERED:
            key = q.question.number
        else:
            key = (q.question.number, i)
        if key not in question_map:
            question_map[key] = q
    # replace or insert at the back
    question_map[question.number] = QuizProblem(question)

    quiz.problems = list(question_map.values())
    repo.quiz.update(quiz)
