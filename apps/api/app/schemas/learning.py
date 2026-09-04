from pydantic import BaseModel


class LessonSection(BaseModel):
    id: str
    heading: str
    body: str


class PracticeTask(BaseModel):
    id: str
    title: str
    objective: str
    requirements: list[str]
    hints: list[str]
