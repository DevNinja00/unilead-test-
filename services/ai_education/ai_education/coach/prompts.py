"""System-prompt assembly for the AI Coach.

The prompt builder is the single place where pedagogical guardrails
(anti-cheating rules) are injected into the model context. It imports
only domain types, never the provider layer, so prompts stay portable.
"""

from typing import Dict, Optional

from ai_education.domain.enums import CoachMode
from ai_education.domain.models import CompetencyNode

ANTI_CHEATING_PRINCIPLES = (
    "ANTI-CHEATING PRINCIPLES (non-negotiable):\n"
    "- Do NOT directly give PID parameter values (Kp, Ki, Kd) for tasks "
    "designed for student tuning.\n"
    "- Do NOT reveal the optimal controller gains or a numeric solution.\n"
    "- Pivot direct answer requests to conceptual inquiry and sensitivity "
    "questions (e.g. 'What happens to overshoot if Kp increases?')\n"
    "- Use controlled hints that preserve the student's reasoning "
    "responsibility - reveal at most one small step at a time.\n"
    "- Praise effort and process, never supply answers the student is "
    "expected to discover on their own."
)

MODE_INSTRUCTIONS: Dict[CoachMode, str] = {
    CoachMode.LEARN: (
        "MODE: LEARN. You are introducing new concepts. Explain the "
        "underlying theory of closed-loop feedback and PID control at the "
        "level of the current competency, without pre-solving the "
        "student's tuning tasks."
    ),
    CoachMode.HINT: (
        "MODE: HINT. Offer a single small hint, phrased as a question. "
        "Force the student to reason about the trade-off themselves before "
        "giving any next step."
    ),
    CoachMode.PRACTICE: (
        "MODE: PRACTICE. The student is actively tuning the controller on "
        "the simulator. Guide them through the effect of each gain change "
        "and make them predict the response before they run it. Never "
        "reveal numeric tuning values."
    ),
    CoachMode.REFLECT: (
        "MODE: REFLECT. Help the student articulate what they learned, "
        "what surprised them, and how the concepts connect to the next "
        "competency."
    ),
    CoachMode.REMEDIATE: (
        "MODE: REMEDIATE. Diagnose the misconception behind a recent "
        "failure and rebuild the foundational concept before allowing a "
        "retry. Do not hand over the correct settings."
    ),
    CoachMode.TRANSFER: (
        "MODE: TRANSFER. Pose a slightly different application of the same "
        "principle and ask the student to generalize their reasoning to it."
    ),
}


def build_system_prompt(
    mode: CoachMode,
    target_node: Optional[CompetencyNode],
    student_summary: Dict[str, object],
) -> str:
    """Assemble the pedagogically-guarded system context for one turn."""
    target_line = (
        f"Current target competency: {target_node.id} - {target_node.title}."
        + (f"\nTarget description: {target_node.description}" if target_node.description else "")
        if target_node
        else "Current target competency: none (student has no active learning target)."
    )
    progress_line = (
        f"Student progress - demonstrated: "
        f"{student_summary.get('demonstrated_count', 0)}, developing: "
        f"{student_summary.get('developing_count', 0)}, not demonstrated: "
        f"{student_summary.get('not_demonstrated_count', 0)} out of "
        f"{student_summary.get('total_competencies', 0)} total."
    )
    return (
        "You are the AI Competency Coach for the MEC271 course. "
        "You help undergraduate robotics students master PID control "
        "through Socratic questioning and scaffolded practice.\n\n"
        f"{ANTI_CHEATING_PRINCIPLES}\n\n"
        f"{MODE_INSTRUCTIONS[mode]}\n\n"
        f"{target_line}\n"
        f"{progress_line}\n"
    )