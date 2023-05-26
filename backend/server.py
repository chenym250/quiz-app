import random
import uuid
from datetime import timedelta

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from quiz_app.repo import new_connection
from quiz_app.models import *


app = FastAPI()
repo = new_connection().get_access_api()


class NewQuizParam(BaseModel):
    topics: list[str]
    shuffle: bool
    total_question: int | None = None
    duration: timedelta | None = None
    name: str | None = None


class QuizDisplay(BaseModel):
    quiz_id: str
    name: str
    topics: list[str]

    size: int
    current_index: int
    is_done: bool
    current_question: Question | None

    create_time: datetime
    update_time: datetime | None = None
    begin_time: datetime | None = None
    done_time: datetime | None = None

    @classmethod
    def from_model(cls, quiz: Quiz) -> 'QuizDisplay':
        index = quiz.current_index
        if index >= 0:
            current = quiz.problems[index]
        else:
            current = None
        return QuizDisplay(
            quiz_id=quiz.id_,
            name=quiz.name,
            topics=quiz.topics,
            size=quiz.size,
            is_done=current is None,
            current_index=index,
            current_question=current,
            create_time=quiz.create_time,
            update_time=quiz.update_time,
            begin_time=quiz.begin_time,
            done_time=quiz.done_time,
        )


@app.get('/topic/{topic_id}')
def get_question(topic_id: str):
    return repo.topic.get(topic_id)


@app.get('/question/{number}')
def get_question(number: str):
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
        id_=id_,
        name=(param.name if param.name else f'quiz:{id_}'),
        topics=sorted({t for q in questions for t in q.of_topics}),
        problems=[QuizProblem(q) for q in questions],
        create_time=now,
    )

    quiz = repo.quiz.add(quiz)
    return QuizDisplay.from_model(quiz)


@app.get('/quiz/{quiz_id}')
def get_quiz(quiz_id: str) -> QuizDisplay:
    quiz = repo.quiz.get(quiz_id)
    return QuizDisplay.from_model(quiz)


@app.get('/quiz/{quiz_id}/question/{question_id}')
def get_quiz_question(quiz_id: str, question_id: str) -> QuizProblem:
    quiz = repo.quiz.get(quiz_id)

    for quiz_question in quiz.problems:
        if quiz_question.question.number == question_id:
            return quiz_question
    else:
        raise HTTPException(status_code=404, detail='question not found')


@app.post('/quiz/{quiz_id}/question/{question_id}')
def submit_question(quiz_id: str, question_id: str, answers: list[str]) -> QuizProblem:
    quiz = repo.quiz.get(quiz_id)

    for quiz_question in quiz.problems:
        if quiz_question.question.number == question_id:
            break
    else:
        raise HTTPException(status_code=404, detail='question not found')

    if quiz_question.status != ProblemAnswerStatus.NOT_ANSWERED:
        raise HTTPException(status_code=400, detail='question already answered')
    quiz_question.user_answer = answers
    try:
        is_correct = quiz_question.question.is_correct(answers)
    except ValueError:
        raise HTTPException(status_code=400, detail='answer not acceptable')

    if is_correct:
        quiz_question.status = ProblemAnswerStatus.CORRECT
    else:
        quiz_question.status = ProblemAnswerStatus.INCORRECT
        update_all_wrong_answer_quiz(quiz_question.question)

    repo.quiz.update(quiz)
    return get_quiz_question(quiz_id, question_id)


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
