"""Pre-configured profiles and telemetry for offline demos.

These fixtures keep live demonstrations deterministic: a presenter can load a
known learner archetype or a known step-response signature without needing a
networked LLM or a re-run of the simulator.
"""

from typing import Dict

DEMO_STUDENT_PROFILES: Dict[str, Dict[str, object]] = {
    "Struggling Sam": {
        "student_id": "demo-struggling-sam",
        "display_name": "Struggling Sam",
        "pace": "STRUGGLING",
        "scaffolding_level": "HIGH",
        "competency_states": {
            "MEC271-FB": "DEVELOPING",
            "MEC271-PID-FUND": "NOT_DEMONSTRATED",
            "MEC271-PID-REASON": "NOT_DEMONSTRATED",
            "MEC271-PID-TUNE": "NOT_DEMONSTRATED",
            "MEC271-RESP-ANALYSIS": "NOT_DEMONSTRATED",
        },
        "known_misconceptions": [
            "EXCESSIVE_PROPORTIONAL_GAIN",
            "UNSTABLE_TUNING",
        ],
    },
    "Progressing Pat": {
        "student_id": "demo-progressing-pat",
        "display_name": "Progressing Pat",
        "pace": "NORMAL",
        "scaffolding_level": "MEDIUM",
        "competency_states": {
            "MEC271-FB": "DEMONSTRATED",
            "MEC271-PID-FUND": "DEMONSTRATED",
            "MEC271-PID-REASON": "DEVELOPING",
            "MEC271-PID-TUNE": "NOT_DEMONSTRATED",
            "MEC271-RESP-ANALYSIS": "NOT_DEMONSTRATED",
        },
        "known_misconceptions": ["MISSING_INTEGRAL_ACTION"],
    },
    "Mastering Morgan": {
        "student_id": "demo-mastering-morgan",
        "display_name": "Mastering Morgan",
        "pace": "FAST",
        "scaffolding_level": "LOW",
        "competency_states": {
            "MEC271-FB": "MASTERED",
            "MEC271-PID-FUND": "MASTERED",
            "MEC271-PID-REASON": "MASTERED",
            "MEC271-PID-TUNE": "DEMONSTRATED",
            "MEC271-RESP-ANALYSIS": "NOT_DEMONSTRATED",
        },
        "known_misconceptions": ["NONE"],
    },
}

DEMO_TELEMETRY_SAMPLES: Dict[str, Dict[str, Dict[str, object]]] = {
    "unstable": {
        "metrics": {
            "overshoot_pct": 0.0,
            "settling_time_sec": 0.0,
            "rise_time_sec": 0.0,
            "steady_state_error": 0.0,
            "is_stable": False,
        },
        "gains": {"kp": 25.0, "ki": 0.0, "kd": 0.0},
    },
    "underdamped": {
        "metrics": {
            "overshoot_pct": 14.0,
            "settling_time_sec": 2.9,
            "rise_time_sec": 0.5,
            "steady_state_error": 0.0,
            "is_stable": True,
        },
        "gains": {"kp": 6.0, "ki": 0.6, "kd": 0.1},
    },
    "well_tuned": {
        "metrics": {
            "overshoot_pct": 5.0,
            "settling_time_sec": 1.1,
            "rise_time_sec": 0.35,
            "steady_state_error": 0.01,
            "is_stable": True,
        },
        "gains": {"kp": 2.0, "ki": 0.5, "kd": 0.8},
    },
}


def get_demo_student_profiles() -> Dict[str, Dict[str, object]]:
    """Return the pre-configured demo learner profiles (fresh copies)."""
    return {
        name: dict(profile) for name, profile in DEMO_STUDENT_PROFILES.items()
    }


def get_demo_telemetry_samples() -> Dict[str, Dict[str, Dict[str, object]]]:
    """Return valid step-response telemetry samples (fresh copies)."""
    return {
        key: (
            dict(sample)
            if isinstance(sample, dict)
            else sample
        )
        for key, sample in DEMO_TELEMETRY_SAMPLES.items()
    }