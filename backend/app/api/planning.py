
from fastapi import APIRouter, status

from app.models.planning import PlanningRequest, PlanningResponse
from app.services.planning_service import planJourney as planJourneyService


router = APIRouter()


@router.post(
    "/plan",
    response_model=PlanningResponse,
    status_code=status.HTTP_200_OK
)
async def planJourney(
    request: PlanningRequest
) -> PlanningResponse:
    return await planJourneyService(request)
