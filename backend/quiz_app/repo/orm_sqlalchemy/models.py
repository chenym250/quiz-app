from enum import Enum
from typing import List
from typing import Optional

from sqlalchemy import Column, Table
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship


class Base(DeclarativeBase):
    pass


class Topic(Base):

    __tablename__ = 'topic'

    id: Mapped[str] = mapped_column(String(31), primary_key=True)  # TODO foreign?
    seq: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column(String(255))
    questions: Mapped[List['Question']] = relationship(
        back_populates='question', cascade='all, delete-orphan'
    )


class Question(Base):
    __tablename__ = 'question'
    id: Mapped[str] = mapped_column(String(31), primary_key=True)
    seq: Mapped[int] = mapped_column()
    topic_id: Mapped[str] = mapped_column(ForeignKey('topic.id'))  # TODO foreign?
    question_type: Mapped[str] = mapped_column(String(255))
    text_segments: Mapped[List['QuestionSegment']] = relationship(
        back_populates='question_segment', cascade='all, delete-orphan',
        secondary=Table(
            "question_segment",
            Base.metadata,
            Column("left_id", ForeignKey("left_table.id")),
            Column("right_id", ForeignKey("right_table.id")),
        )
    )


class Segment(Base):
    __tablename__ = 'segment'
    id: Mapped[int] = mapped_column(primary_key=True)
    segment_type: Mapped[str] = mapped_column(String(30))
    segment_header: Mapped[str] = mapped_column(String(30))
    text: Mapped[str] = mapped_column(String(1024))
