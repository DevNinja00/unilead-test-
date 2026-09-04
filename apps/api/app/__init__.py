"""Unilead API application package.

Importing this package registers the ``services/ai_education`` library on
``sys.path`` so it is importable without pip-installing it. Doing this in
the package ``__init__`` (rather than relying on ``import app.config``
coming first) means ``from ai_education import ...`` works anywhere in the
app regardless of import order. See also the identical bootstrap in
``app.config`` (kept for standalone script usage); both are idempotent.
"""

import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent  # apps/api/app
_API_DIR = _APP_DIR.parent  # apps/api
_REPO_ROOT = _API_DIR.parents[1]  # apps -> repo root
_AI_EDUCATION_DIR = _REPO_ROOT / "services" / "ai_education"

for _directory in (str(_AI_EDUCATION_DIR), str(_API_DIR)):
    if _directory not in sys.path:
        sys.path.insert(0, _directory)
