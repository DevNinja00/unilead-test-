from . import student_state
from .mock_data import EVIDENCE_TEMPLATE

# How much progress completing a review folds back into the competency /
# overall course progress. Kept small and fixed for the MVP demo.
PROGRESS_BUMP = 20
OVERALL_BUMP = 8


def get_review(competency_id: str | None, finalize: bool, student_id: str) -> dict:
    """Return the evidence review for the given competency (or the active
    one). If ``finalize=True`` and the competency is still developing,
    bump the progress and overall score.
    """
    competency = (
        student_state.get_competency(competency_id, student_id)
        if competency_id
        else student_state.get_active_competency(student_id)
    )
    if competency is None:
        competency = student_state.get_active_competency(student_id)

    if finalize and competency["status"] == "developing":
        student_state.bump_competency_progress(competency["id"], PROGRESS_BUMP, student_id)
        student_state.bump_overall_progress(OVERALL_BUMP, student_id)
        # re-read after mutation so the response reflects the new numbers
        competency = student_state.get_competency(competency["id"], student_id)

    return {
        "competency_id": competency["id"],
        "competency_name": competency["name"],
        "status": competency["status"],
        "progress": competency["progress"],
        "overall_progress": student_state.get_overall_progress(student_id),
        "evidence": EVIDENCE_TEMPLATE,
    }
