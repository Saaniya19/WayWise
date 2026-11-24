from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models.common import Location
from app.services.journey_composer import compose_journey


origin = Location(
    name="University of Waterloo",
    latitude=43.4723,
    longitude=-80.5449,
)

parking = Location(
    name="Kitchener GO Parking",
    latitude=43.4550,
    longitude=-80.4790,
)

boarding = Location(
    name="Kitchener GO Station",
    latitude=43.4555,
    longitude=-80.4785,
)

destination = Location(
    name="CN Tower",
    latitude=43.6426,
    longitude=-79.3871,
)

departure_time = datetime.now(timezone.utc) + timedelta(minutes=5)

journey = compose_journey(
    origin=origin,
    destination=destination,
    parking_location=parking,
    boarding_location=boarding,
    departure_time=departure_time,
)

if journey is None:
    print("No feasible journey found.")
else:
    print(journey.model_dump_json(indent=2))

    local_tz = ZoneInfo("America/Toronto")

    print("\n===== JOURNEY SUMMARY =====")

    for segment in journey.segments:
        start = segment.startTime.astimezone(local_tz)
        end = segment.endTime.astimezone(local_tz)

        print(
            f"{segment.kind}: "
            f"{start.strftime('%H:%M:%S')} - "
            f"{end.strftime('%H:%M:%S')} "
            f"({segment.durationSeconds / 60:.1f} min)"
        )

    print(f"\nTotal duration: {journey.totalDurationSeconds / 60:.1f} min")
    print(f"Transfers: {journey.transferCount}")
