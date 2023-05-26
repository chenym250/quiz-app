import dataclasses
import itertools
import re
from collections import defaultdict, namedtuple
from enum import Enum
from typing import Iterable, Iterator, TypeVar, Generic

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTPage, LTTextBox, LTChar, LAParams, LTComponent

from quiz_app.models import Topic, Choice, QuestionType
from quiz_app.models import Question, MultiAnswer, MultiChoice


@dataclasses.dataclass(frozen=True)
class Font:
    name: str
    size: str


class FontType(Enum):
    TABLE = Font('IPCIKH+FZKTK--GBK1-0', 10)
    TITLE = Font('ILROKH+AlibabaPuHuiTiR', 16)
    TITLE_2 = Font('ILROKH+AlibabaPuHuiTiR', 18)
    SECTION = Font('GAUHIL+AlibabaPuHuiTiM', 10)
    INDEX = Font('ILROKH+AlibabaPuHuiTiR', 10)
    INDEX_2 = Font('ILROKH+AlibabaPuHuiTiR', 9)
    TEXT = Font('FBDPUN+FZSSK--GBK1-0', 10)
    OTHER = Font('', 0)

    def char_matches(self, char: LTChar) -> bool:
        font = self.value
        if font.name != char.fontname:
            return False
        return abs(font.size - char.size) < 1e-3

    def textbox_matches(self, textbox: LTTextBox, mode=all) -> bool:
        return mode(
            self.char_matches(c)
            for line in textbox
            for c in line
            if isinstance(c, LTChar)
        )


@dataclasses.dataclass(frozen=True)
class BBox:
    x0: int
    y0: int
    x1: int
    y1: int

    @classmethod
    def from_element(cls, element: LTComponent) -> 'BBox':
        return cls(x0=int(element.x0), y0=-int(element.y0), x1=int(element.x1), y1=-int(element.y1))

    def translate(self, vector: tuple[int, int]) -> 'BBox':
        return self.__class__(
            x0=self.x0 + vector[0],
            y0=self.y0 + vector[1],
            x1=self.x1 + vector[0],
            y1=self.y1 + vector[1],
        )

    def with_new(self, **kwargs) -> 'BBox':
        return self.__class__(
            x0=kwargs.get('x0', self.x0),
            y0=kwargs.get('y0', self.y0),
            x1=kwargs.get('x1', self.x1),
            y1=kwargs.get('y1', self.y1),
        )

    def contains(self, another: 'BBox') -> bool:
        return self.x0 < another.x0 and self.x1 > another.x1 and self.y0 < another.y0 and self.y1 > another.y1


T = TypeVar('T')


class Peekable(Iterator[T]):

    iter: Iterator[T]
    cache: T | None

    def __init__(self, iter: Iterator[T]):
        self.iter = iter

    def __iter__(self) -> Iterator[T]:
        return self

    def __next__(self) -> T:
        if self.cache:
            cached = self.cache
            self.cache = None
            return cached
        return next(self.iter)

    def peek(self) -> T:
        if self.cache is None:
            self.cache = next(self.iter)
        return self.cache


def cn_num_convert(s: str) -> int:
    from cn2an import cn2an
    return cn2an(s, 'normal')


def get_filename():
    import sys
    if len(sys.argv) != 2:
        raise RuntimeError('no file specified')
    return sys.argv[1]


@dataclasses.dataclass
class Cursor:
    page_no: int
    component: LTComponent = dataclasses.field(hash=False, compare=False)

    @property
    def has_text(self) -> bool:
        return isinstance(self.component, LTTextBox)


@dataclasses.dataclass
class SectionCursor(Cursor):
    title: str | None = None
    section_title: str | None = None


def read_components(pages: Iterator[LTPage]) -> Iterator[Cursor]:
    for page in pages:
        for component in sorted(page, key=lambda ele: (-int(ele.y0), int(ele.x0))):
            yield Cursor(page_no=page.pageid, component=component)


def read_sections(pages: Iterator[LTPage]) -> Iterator[SectionCursor]:
    title, section_title = None, None

    def make_cursor(base: Cursor) -> SectionCursor:
        return SectionCursor(
            page_no=base.page_no,
            component=base.component,
            title=title,
            section_title=section_title
        )

    for _, cursors in itertools.groupby(read_components(pages), key=lambda c: c.page_no):
        cached = []
        for cursor in cursors:
            if cursor.has_text:
                break
            cached.append(cursor)
        else:
            # no text on this page
            yield from map(make_cursor, cached)
            continue

        # prcess first text component
        if any(font_type.textbox_matches(cursor.component) for font_type in (FontType.TITLE, FontType.TITLE_2)):
            # title should be the first text line
            title = cursor.component.get_text().strip()
            section_title = None
        else:
            # title component itself is ignored.
            cursors = itertools.chain([cursor], cursors)

        yield from map(make_cursor, cached)
        cached = []

        for cursor in cursors:
            if cursor.has_text and FontType.SECTION.textbox_matches(cursor.component):
                section_title = cursor.component.get_text().strip()
            else:
                # section title component itself is also ignored.
                yield make_cursor(cursor)


class ChapterReader(Iterator[Topic]):
    CHAPTER_TITLE = r'第(?P<idx_cn>[一二三四五六七八九十]+)章\s*(?P<title>.*)\s*+'
    TOPIC_TITLE = r'专题(?P<idx_cn>[一二三四五六七八九十]+)\s*(?P<title>.*)\s*+'
    ANSWER_CHOICES = r'\s*([ABCD]+)\s+(.*)'
    ANSWER_SHEET = r'[\sA-Z0-9\.]+'

    # a helper class
    ChapterTitle = namedtuple('ChapterTitle', ('id_', 'title'))

    # for storing question related data before publishing
    class QAs:
        raw_questions: dict[str, list[str]]
        raw_answers: dict[str, list[str]]
        question_types: dict[str, QuestionType]
        question_refs: dict[str, Question]

        def __init__(self):
            self.raw_questions = defaultdict(list)
            self.raw_answers = defaultdict(list)
            self.question_types = {}
            self.question_refs = {}

    @staticmethod
    def _make_chapter(title: 'ChapterReader.ChapterTitle', qa: 'ChapterReader.QAs') -> Topic:
        chapter = Topic(
            topic_id=title.id_,
            name=title.title
        )

        # add question text
        for index, lines in qa.raw_questions.items():
            question_type = qa.question_types[index]
            question = question_type.new_question(index, '')
            question.topic_id = chapter.topic_id

            if question_type in (QuestionType.MULTI_CHOICE, QuestionType.MULTI_ANSWER):
                choices = defaultdict(lambda: '')
                choice = None
                for line in lines:
                    if line[0] in ('A', 'B', 'C', 'D') and line[1] == '.':
                        choice = line[0]
                        line = line[2:]
                    if choice is not None:
                        choices[choice] += line.strip()
                    else:
                        question.text += line
                question.choices = [Choice(c, t) for c, t in choices.items()]
            else:
                question.text += ''.join(lines)

            question.text = ChapterReader._strip_text(index, question.text)
            qa.question_refs[index] = question
            chapter.questions.append(question)

        # add answers
        for index, lines in qa.raw_answers.items():
            if not lines:
                raise RuntimeError

            question = qa.question_refs[index]
            question_type = qa.question_types[index]

            text = ChapterReader._strip_text(index, ''.join(lines))

            if question_type in (QuestionType.MULTI_CHOICE, QuestionType.MULTI_ANSWER):
                m = re.match(ChapterReader.ANSWER_CHOICES, text, re.U)
                if not m:
                    raise RuntimeError
                answer, _ = m.groups()
                text = text[len(answer):].strip()
                if question_type == QuestionType.MULTI_CHOICE:
                    question.answer = answer
                else:
                    question.answer = tuple(answer)

            qa.question_refs[index].explain = text

        return chapter

    @staticmethod
    def _strip_text(index: str, lines: Iterable[str]) -> str:
        text = ''.join(lines).replace('斯尔解析', '').strip()
        if text.startswith(index):
            text = text[len(index):]
        text = text.strip()
        return text

    # flow control
    stream: Iterator[tuple[SectionCursor, Iterator[Cursor]]]
    is_done: bool

    def __init__(self, pages: Iterator[LTPage]):
        self.stream = itertools.groupby(read_sections(pages))
        self.is_done = False

    def __iter__(self) -> Iterator[Topic]:
        return self

    def __next__(self) -> Topic:
        if self.is_done:
            raise StopIteration

        chapter: tuple[ChapterReader.ChapterTitle, ChapterReader.QAs] | None = None
        prev_title = None
        prev_idx = None
        is_answer_phase = False

        for section, cursors in self.stream:
            if section.title is None:
                continue

            # handle cases where title changes (new chapter, end of chapter, etc.)
            if prev_title != section.title:
                prev_title = section.title
                chapter_title, is_answer, is_end = self._read_chapter_titles(section.title)

                if is_end:
                    # end of chapter
                    if chapter is not None:
                        # this function ends here
                        return self._make_chapter(*chapter)
                    continue

                elif is_answer:
                    assert chapter is not None
                    is_answer_phase = True
                    prev_idx = None

                elif chapter_title is None:
                    # not a recordable chapter (e.g. table of contents)
                    assert chapter is None
                    continue

                else:
                    assert chapter is None
                    chapter = (chapter_title, self.QAs())

            if chapter is None:
                continue

            # infer section type
            section_question_type = None
            if section.section_title is not None:
                for q_type in QuestionType:
                    if q_type.value in section.section_title:
                        section_question_type = q_type
                        break

            # read indices
            qa: ChapterReader.QAs = chapter[1]
            index_mapping = _read_indices((c.component for c in cursors), prev_index=prev_idx, is_sorted=True)
            for index, components in index_mapping:
                if index is None:
                    raise RuntimeError
                prev_idx = index
                lines = [c.get_text() for c in components if isinstance(c, LTTextBox)]
                if not lines:
                    continue
                if is_answer_phase:
                    if re.fullmatch(self.ANSWER_SHEET, ''.join(lines), re.U):
                        # answer sheet, ignore for now
                        continue
                    qa.raw_answers[index].extend(lines)

                    # infer question type
                    question_type = qa.question_types.get(index)
                    if question_type is None:
                        m = re.match(self.ANSWER_CHOICES, self._strip_text(index, ''.join(lines)), re.U)
                        if not m:
                            question_type = QuestionType.SHORT_ANSWER
                        elif len(m.group(1)) == 1:
                            question_type = QuestionType.MULTI_CHOICE
                        else:
                            question_type = QuestionType.MULTI_ANSWER
                        qa.question_types[index] = question_type
                    if section_question_type is not None and question_type != section_question_type:
                        raise RuntimeError

                else:
                    qa.raw_questions[index].extend(lines)
                    if section_question_type is not None and index not in qa.question_types:
                        qa.question_types[index] = section_question_type

        # else:
        # end of stream
        self.is_done = True
        if chapter is not None:
            return self._make_chapter(*chapter)
        else:
            raise StopIteration

    def _read_chapter_titles(self, title: str) -> tuple[ChapterTitle | None, bool, bool]:
        if title == '错题整理页':
            # ignore
            return None, False, True

        if title == '答案与解析':
            return None, True, False

        m = re.match(self.CHAPTER_TITLE, title)
        if m:
            attrs = m.groupdict()
            id_ = 'chapter-' + str(cn_num_convert(attrs['idx_cn']))
            title = attrs['title']
        else:
            m = re.match(self.TOPIC_TITLE, title)
            if not m:
                # title not match; ignore
                return None, False, False
            attrs = m.groupdict()
            id_ = 'topic-' + str(cn_num_convert(attrs['idx_cn']))
            title = attrs['title']
        return self.ChapterTitle(id_=id_, title=title), False, False


def _read_indices(
        elements: Iterator[LTComponent],
        prev_index: str | None = None,
        is_sorted=False,
        left_ref: float | None = None) -> Iterable[tuple[str, list[LTComponent]]]:
    """
    elements should ideally come from the same page.
    """
    elements = list(elements)
    if not is_sorted:
        elements.sort(key=lambda ele: (-int(ele.y0), int(ele.x0)))

    try:
        left_most = min(ele.x0 for ele in elements if isinstance(ele, LTTextBox))
        right_most = max(ele.x1 for ele in elements if isinstance(ele, LTTextBox))
        bottom = max(-ele.y1 for ele in elements if isinstance(ele, LTTextBox) and not re.match(r'·\s*\d+\s*·', ele.get_text(), re.U))
    except ValueError:
        return []
    if left_ref is not None and left_most > left_ref:
        left_most = left_ref

    delta = 5
    index_and_locations: list[tuple[str, BBox]] = []

    for ele in elements:
        if not isinstance(ele, LTTextBox):
            continue
        if ele.x0 > left_most + delta:
            continue
        if not FontType.INDEX.textbox_matches(ele, mode=any):
            continue
        m = re.match(r'\s*(\d+\.\d+)+', ele.get_text(), flags=re.U)
        if not m:
            continue

        location = BBox(
            x0=ele.x0 - delta,
            y0=-ele.y0 - delta,
            x1=right_most + delta,
            y1=bottom + delta
        )
        index_and_locations.append((m.group(1), location))
        if len(index_and_locations) > 1:
            index_and_locations[-2] = (
                index_and_locations[-2][0],
                index_and_locations[-2][1].with_new(y1=location.y0),
            )
    if not index_and_locations:
        return []

    result = defaultdict(list)

    curr_idx, curr_bbox = index_and_locations.pop(0)
    is_prev = True
    for ele in elements:
        while -ele.y0 > curr_bbox.y1:
            # box higher than ele
            is_prev = False
            try:
                curr_idx, curr_bbox = index_and_locations.pop(0)
            except IndexError:
                break

        loc = BBox.from_element(ele)
        if curr_bbox.contains(loc):
            is_prev = False
            result[curr_idx].append(ele)
        elif is_prev and prev_index is not None:
            result[prev_index].append(ele)

    return ((k, v) for k, v in result.items() if any(isinstance(c, LTTextBox) for c in v))


def pretty(question: Question) -> str:
    text = f'{question.number} {"".join(question.text)}'
    if isinstance(question, (MultiChoice, MultiAnswer)):
        text += '\n\n'
        for choice in question.choices:
            text += f'{choice.letter}. {choice.text}\n'
        text += '\n答案: ' + ''.join(question.answer) + '\n'

    text += '\n解析:\n' + question.explain
    return text


if __name__ == '__main__':
    file_name = get_filename()

    import shutil
    from pathlib import Path

    result_dir = Path('json')
    if result_dir.exists():
        shutil.rmtree(result_dir)
    result_dir.mkdir(exist_ok=True)

    from quiz_app import repo
    repo_api = repo.new_connection().get_access_api()
    # clear DB
    for chapter_id in repo_api.topic.list_ids():
        repo_api.topic.delete(chapter_id)

    for chapter in ChapterReader(extract_pages(file_name)):
        print(chapter)

        fdir = result_dir.joinpath(f'{chapter.topic_id}_{chapter.name}')
        fdir.mkdir(exist_ok=True)
        for question in chapter.questions:
            fpath = fdir.joinpath(f'{question.number}.txt')
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(pretty(question))

        repo_api.topic.add(chapter)
