
from datetime import datetime, timezone
from uuid import uuid4

from app.models.planning import PlanningRequest, PlanningResponse


async def planJourney(
    request: PlanningRequest
) -> PlanningResponse:
    departureTime = datetime.now(timezone.utc)

    return PlanningResponse(
        requestId=str(uuid4()),
        departureTime=departureTime,
        journeys=[],
        isPartial=False,
        errors=[]
    )
