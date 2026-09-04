from .mock_data import LESSON_SECTIONS, PRACTICE_TASKS


def get_lesson(competency_id: str) -> list[dict]:
    return LESSON_SECTIONS.get(competency_id, LESSON_SECTIONS["pid-reasoning"])


def get_practice_task(competency_id: str) -> dict:
    return PRACTICE_TASKS.get(competency_id, PRACTICE_TASKS["pid-reasoning"])
