"""PID simulation router — runs a real simulation for the current student."""

from fastapi import APIRouter, Depends, Request

from ..auth.dependencies import get_current_student
from ..db.models import Student
from ..schemas.simulation import SimulationRequest, SimulationResult
from ..services import simulation_service

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


@router.post("", response_model=SimulationResult)
def run_simulation(
    request: SimulationRequest,
    http_request: Request,
    current_student: Student = Depends(get_current_student),
) -> dict:
    """Run a PID simulation with the given gains and record the evidence
    for the current student.
    """
    return simulation_service.run_simulation(request, http_request, current_student.student_id)
