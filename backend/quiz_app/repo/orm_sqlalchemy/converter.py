from backend.models import Topic, Choice, Question, QuestionType
from .models import Chapter as ChapterORM, Question as QuestionORM, QuestionSegment as QuestionSegmentORM


def convert_question(question: Question, chapter_id: str | None = None) -> QuestionORM:
    orm = QuestionORM(id=question.number)
    if chapter_id is not None:
        orm.chapter_id = chapter_id
    orm.question_type = str(question.question_type)
    orm.text = question.text
    segments = []
    index = 0
    if question.question_type in QuestionType.MULTI_CHOICE or QuestionType.MULTI_ANSWER:
        for choice in question.choices:
            choice: Choice
            segments.append(QuestionSegmentORM(question_id=question.number, index=index, segment_type='CHOICE', segment_header=choice.letter, text=choice.text))
            index += 1
    orm.segments = segments
