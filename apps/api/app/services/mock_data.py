"""
Static mock content for the MEC271 — Automatic Control demo.

This is content, not state: it never changes at runtime. Mutable student
progress lives separately in services/student_state.py.
"""

COURSE_CODE = "MEC271"
COURSE_TITLE = "Automatic Control"

# The initial competency set. Every new student starts at zero — no
# demonstrated competencies, no progress. Whatever they demonstrate is
# earned through the loop (diagnostic → learn → practice → simulation →
# transfer). The Compass services read+write this to the DB.
INITIAL_COMPETENCIES = [
    {"id": "feedback-fundamentals", "name": "Feedback Fundamentals", "status": "not_started", "progress": 0},
    {"id": "pid-fundamentals", "name": "PID Fundamentals", "status": "not_started", "progress": 0},
    {"id": "pid-reasoning", "name": "PID Reasoning", "status": "not_started", "progress": 0},
    {"id": "pid-tuning", "name": "PID Tuning", "status": "not_started", "progress": 0},
    {"id": "response-analysis", "name": "Response Analysis", "status": "not_started", "progress": 0},
]

INITIAL_OVERALL_PROGRESS = 0

DIAGNOSTIC_QUESTIONS = [
    {
        "id": "q1",
        "competency_id": "feedback-fundamentals",
        "prompt": "In a closed-loop system, what is the purpose of feedback?",
        "options": [
            {"id": "a", "label": "To amplify the input signal"},
            {"id": "b", "label": "To compare output to a desired reference and correct error"},
            {"id": "c", "label": "To remove noise from the sensor only"},
            {"id": "d", "label": "To slow down the system response"},
        ],
    },
    {
        "id": "q2",
        "competency_id": "pid-fundamentals",
        "prompt": "Which PID term responds to how fast the error is changing?",
        "options": [
            {"id": "a", "label": "Proportional"},
            {"id": "b", "label": "Integral"},
            {"id": "c", "label": "Derivative"},
            {"id": "d", "label": "None of the above"},
        ],
    },
    {
        "id": "q3",
        "competency_id": "pid-reasoning",
        "prompt": "If you increase Kp significantly, what typically happens to overshoot?",
        "options": [
            {"id": "a", "label": "Overshoot decreases"},
            {"id": "b", "label": "Overshoot usually increases"},
            {"id": "c", "label": "Overshoot is unaffected"},
            {"id": "d", "label": "The system becomes open-loop"},
        ],
    },
    {
        "id": "q4",
        "competency_id": "pid-tuning",
        "prompt": "What is a common goal when tuning a PID controller?",
        "options": [
            {"id": "a", "label": "Maximize settling time"},
            {"id": "b", "label": "Meet requirements for overshoot, settling time, and steady-state error"},
            {"id": "c", "label": "Remove the integral term entirely"},
            {"id": "d", "label": "Ignore steady-state error"},
        ],
    },
    {
        "id": "q5",
        "competency_id": "response-analysis",
        "prompt": "Rise time refers to the time it takes for the response to:",
        "options": [
            {"id": "a", "label": "Reach steady state exactly"},
            {"id": "b", "label": "Go from 10% to 90% of its final value"},
            {"id": "c", "label": "Overshoot the reference"},
            {"id": "d", "label": "Decay to zero"},
        ],
    },
]

LESSON_SECTIONS = {
    "pid-reasoning": [
        {
            "id": "sec-1",
            "heading": "What is PID Reasoning?",
            "body": (
                "PID reasoning is the ability to predict how a system will respond when you "
                "change the proportional, integral, or derivative gains — before you actually "
                "run the simulation."
            ),
        },
        {
            "id": "sec-2",
            "heading": "Proportional Gain (Kp)",
            "body": (
                "Increasing Kp generally speeds up the response and reduces steady-state error, "
                "but pushing it too high increases overshoot and can destabilize the system."
            ),
        },
        {
            "id": "sec-3",
            "heading": "Why Prediction Matters",
            "body": (
                "Before tuning a real controller, engineers reason about expected behavior "
                "first. This prevents costly trial-and-error on physical systems."
            ),
        },
    ],
}

PRACTICE_TASKS = {
    "pid-reasoning": {
        "id": "pid-001",
        "title": "Predict the Effect of Increasing Kp",
        "objective": "Practice reasoning about controller behavior before running a simulation.",
        "requirements": [
            "Explain what happens to rise time as Kp increases",
            "Explain what happens to overshoot as Kp increases",
            "Identify one risk of setting Kp too high",
        ],
        "hints": [
            "Think about how quickly the system reacts to error",
            "Consider the trade-off between speed and stability",
        ],
    },
}

# The coach's side of a scripted reasoning dialogue, cycled through as the
# student replies.
COACH_SCRIPT = [
    "What do you expect to happen to rise time if you increase Kp?",
    "Good — and what might happen to overshoot as a result?",
    "Right. Why do you think overshoot increases as Kp gets larger?",
    "Exactly — the system reacts faster but overcorrects. That's solid reasoning.",
    "You've shown a clear understanding here. Ready to try it in Practice?",
]

SIMULATION_RESULT = {
    "stable": True,
    "overshoot": 8.4,
    "settling_time": 1.72,
    "rise_time": 0.48,
    "steady_state_error": 0.003,
}

# Evidence template shown in Review. `met` for "transfer" stays False —
# it genuinely hasn't happened yet in this MVP (no Transfer Task built).
EVIDENCE_TEMPLATE = [
    {"id": "diagnostic", "label": "Diagnostic demonstrated understanding", "met": True},
    {"id": "reasoning", "label": "Reasoning demonstrated with AI Coach", "met": True},
    {"id": "simulation", "label": "Simulation requirement met", "met": True},
    {"id": "transfer", "label": "Transfer not demonstrated yet", "met": False},
]
