"""Tutor chat endpoints (GR-1..GR-5, LM-3)."""
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import LimitedDep
from app.assess import service
from app.qa.chat import ask

router = APIRouter(dependencies=[LimitedDep])
STUDENT_PATTERN = r"^[a-f0-9]{32}$"


class ChatIn(BaseModel):
    student_id: str | None = Field(default=None, pattern=STUDENT_PATTERN)
    question: str = Field(min_length=1, max_length=1000)
    allow_outside: bool = False
    lang: Literal["en", "hi"] = "en"


class CheckAnswerIn(BaseModel):
    student_id: str = Field(pattern=STUDENT_PATTERN)
    question_id: str = Field(max_length=40)
    response: str = Field(min_length=1, max_length=2000)


@router.post("/chat")
def chat(body: ChatIn) -> dict:
    return ask(body.question, body.student_id, body.allow_outside, body.lang)


@router.post("/chat/check")
def answer_check_question(body: CheckAnswerIn) -> dict:
    return service.submit_check(body.student_id, body.question_id, body.response)
