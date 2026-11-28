from datetime import datetime, timedelta, timezone
from haversine import haversine, Unit
from uuid import uuid4
from pydantic import ValidationError

from app.config import (
    DROP_OFF_ACCESS_BUFFER_SECONDS,
    PARKING_DURATION_SECONDS,
    GOOGLE_SNAPPING_TOLERANCE_METERS,
    SEGMENT_CONTINUITY_TOLERANCE_METERS,
)
from app.models.common import Location
from app.models.journey import (
    Journey,
    JourneySegment,
    TransitDetails,
)
from app.models.routing import Route, Segment, TravelMode
from app.services.google_routes_client import get_routes
from app.services.timing_service import checkConnection
from app.models.journey import SegmentKind

import polyline
import logging

logger = logging.getLogger(__name__)

def merge_polylines(
    first: str | None,
    second: str | None,
) -> str | None:
    if not first or not second:
        logger.debug(
            "Cannot merge polylines: missing segment geometry"
        )
        return None

    first_points = polyline.decode(first)
    second_points = polyline.decode(second)

    # Avoid duplicating the shared endpoint.
    if first_points and second_points:
        if first_points[-1] == second_points[0]:
            second_points = second_points[1:]

    return polyline.encode(first_points + second_points)


# checks whether two locations are within a specified
# distance tolerance (using haversine)
def locations_match(
    first: Location,
    second: Location,
    tolerance_meters: float,
) -> bool:
    distance = haversine(
        (first.latitude, first.longitude),
        (second.latitude, second.longitude),
        unit=Unit.METERS,
    )

    return distance <= tolerance_meters
    

# constructs a journey segment from explicitly provided params
def make_segment(
    kind: SegmentKind,
    start_location: Location,
    end_location: Location,
    start_time: datetime,
    duration_seconds: int,
    distance_meters: float | None = None,
    encoded_polyline: str | None = None,
    transit_details: TransitDetails | None = None,
) -> JourneySegment:

    return JourneySegment(
        id=str(uuid4()),
        kind=kind,
        startLocation=start_location,
        endLocation=end_location,
        startTime=start_time,
        endTime=start_time + timedelta(
            seconds=duration_seconds
        ),
        durationSeconds=duration_seconds,
        distanceMeters=distance_meters,
        encodedPolyline=encoded_polyline,
        transitDetails=transit_details,
    )
    

# validates an existing route and extracts its params before
# passing them to make_segment()
def make_route_segment(
    route: Route,
    kind: str,
    origin: Location,
    destination: Location,
    start_time: datetime,
) -> JourneySegment | None:

    if (
        route.duration_seconds is None
        or route.duration_seconds < 0
        or route.distance_meters is None
        or route.start_location is None
        or route.end_location is None
    ):
        return None

    if not locations_match(
        origin,
        route.start_location,
        GOOGLE_SNAPPING_TOLERANCE_METERS,
    ):
        logger.debug(
            "Rejecting %s route: endpoint exceeds snapping tolerance",
            kind,
        )
        return None

    if not locations_match(
        destination,
        route.end_location,
        GOOGLE_SNAPPING_TOLERANCE_METERS,
    ):
        logger.debug(
            "Rejecting %s route: endpoint exceeds snapping tolerance",
            kind,
        )
        return None

    return make_segment(
        kind=kind,
        start_location=route.start_location,
        end_location=route.end_location,
        start_time=start_time,
        duration_seconds=route.duration_seconds,
        distance_meters=route.distance_meters,
        encoded_polyline=route.encoded_polyline,
    )

def compose_walking_step(
    step: Segment,
    current_location: Location,
    current_time: datetime,
) -> JourneySegment | None:

    if (
        step.duration_seconds is None
        or step.duration_seconds < 0
        or step.distance_meters is None
        or step.start_location is None
        or step.end_location is None
    ):
        logger.debug(
            "Rejecting walking step: missing or invalid step data"
        )
        return None

    if not locations_match(
        current_location,
        step.start_location,
        SEGMENT_CONTINUITY_TOLERANCE_METERS,
    ):
        logger.debug(
            "Rejecting walking step: geographical discontinuity"
        )
        return None

    return make_segment(
        kind="WALK",
        start_location=step.start_location,
        end_location=step.end_location,
        start_time=current_time,
        duration_seconds=step.duration_seconds,
        distance_meters=step.distance_meters,
        encoded_polyline=step.encoded_polyline,
    )
    

def compose_transit_step(
    step: Segment,
    current_location: Location,
    current_time: datetime,
) -> list[JourneySegment] | None:

    segments = []
    details = step.transit_details

    if (
        details is None
        or details.departure_time is None
        or details.arrival_time is None
        or details.departure_stop is None
        or details.arrival_stop is None
        or details.departure_stop.location is None
        or details.arrival_stop.location is None
    ):
        logger.debug(
            "Rejecting transit step: missing required transit details"
        )
        return None

    if (
        details.departure_time.utcoffset() is None
        or details.arrival_time.utcoffset() is None
    ):
        logger.debug(
            "Rejecting transit step: timestamps are not timezone-aware"
        )
        return None

    departure = details.departure_time.astimezone(
        timezone.utc
    ).replace(microsecond=0)

    arrival = details.arrival_time.astimezone(
        timezone.utc
    ).replace(microsecond=0)

    if arrival <= departure:
        logger.debug(
            "Rejecting transit step: invalid ride timing"
        )
        return None

    boarding_stop = details.departure_stop.location
    alighting_stop = details.arrival_stop.location

    if not locations_match(
        current_location,
        boarding_stop,
        SEGMENT_CONTINUITY_TOLERANCE_METERS,
    ):
        logger.debug(
            "Rejecting transit step: discontinuity at boarding stop"
        )
        return None

    connection = checkConnection(
        current_time,
        departure,
        minBufferSeconds=0,
    )

    if not connection.isFeasible:
        logger.debug(
            "Rejecting transit step: infeasible connection "
            "(traveller arrival=%s, service departure=%s)",
            current_time,
            departure,
        )
        return None

    wait_seconds = (
        departure - current_time
    ).total_seconds()

    ride_seconds = (
        arrival - departure
    ).total_seconds()

    if wait_seconds > 0:
        segments.append(
            make_segment(
                kind="WAIT",
                start_location=current_location,
                end_location=current_location,
                start_time=current_time,
                duration_seconds=int(wait_seconds),
            )
        )

    transit_details = TransitDetails(
        agencyName=details.agency_name,
        serviceName=details.line_name,
        routeShortName=details.route_short_name,
        vehicleType=details.vehicle_type,
        boardingStop=boarding_stop,
        alightingStop=alighting_stop,
        headsign=details.headsign,
        stopCount=details.stop_count,
        timingBasis="SCHEDULED",
    )

    segments.append(
        make_segment(
            kind="TRANSIT",
            start_location=boarding_stop,
            end_location=alighting_stop,
            start_time=departure,
            duration_seconds=int(ride_seconds),
            distance_meters=step.distance_meters,
            encoded_polyline=step.encoded_polyline,
            transit_details=transit_details,
        )
    )

    return segments


# converts a Google transit route into individual walking,
# waiting, and transit segments, while checking connection
# feasibility and ensuring continuity
def compose_transit_segments(
    route: Route,
    boarding_location: Location,
    destination: Location,
    start_time: datetime,
) -> list[JourneySegment] | None:

    if (
        route.start_location is None
        or route.end_location is None
    ):
        logger.debug(
            "Rejecting transit route: missing route endpoints"
        )
        return None

    if not locations_match(
        boarding_location,
        route.start_location,
        GOOGLE_SNAPPING_TOLERANCE_METERS,
    ):
        logger.debug(
            "Rejecting transit route: start exceeds snapping tolerance"
        )
        return None

    if not locations_match(
        destination,
        route.end_location,
        GOOGLE_SNAPPING_TOLERANCE_METERS,
    ):
        logger.debug(
            "Rejecting transit route: end exceeds snapping tolerance"
        )
        return None

    segments = []
    current_time = start_time
    current_location = boarding_location
    transit_count = 0

    for leg in route.legs:
        for step in leg.segments:

            if step.mode == TravelMode.WALK:
                segment = compose_walking_step(
                    step,
                    current_location,
                    current_time,
                )

                if segment is None:
                    return None

                segments.append(segment)

            elif step.mode == TravelMode.TRANSIT:
                transit_segments = compose_transit_step(
                    step,
                    current_location,
                    current_time,
                )

                if transit_segments is None:
                    return None

                segments.extend(transit_segments)
                transit_count += 1

            else:
                logger.debug(
                    "Rejecting transit route: unsupported step mode %s",
                    step.mode,
                )
                return None

            current_time = segments[-1].endTime
            current_location = segments[-1].endLocation

    if transit_count == 0:
        logger.debug(
            "Rejecting transit route: no transit segments found"
        )
        return None

    if not locations_match(
        current_location,
        route.end_location,
        SEGMENT_CONTINUITY_TOLERANCE_METERS,
    ):
        logger.debug(
            "Rejecting transit route: final endpoint discontinuity"
        )
        return None

    return segments
    

# combines any consecutive walking segments
def merge_walking_segments(
    segments: list[JourneySegment],
) -> list[JourneySegment]:

    merged = []

    for segment in segments:

        if (
            merged
            and merged[-1].kind == "WALK"
            and segment.kind == "WALK"
            and merged[-1].endTime == segment.startTime
            and locations_match(
                merged[-1].endLocation,
                segment.startLocation,
                SEGMENT_CONTINUITY_TOLERANCE_METERS,
            )
        ):
            previous = merged.pop()

            distance = None

            if (
                previous.distanceMeters is not None
                and segment.distanceMeters is not None
            ):
                distance = (
                    previous.distanceMeters
                    + segment.distanceMeters
                )

            merged.append(
                make_segment(
                    kind="WALK",
                    start_location=previous.startLocation,
                    end_location=segment.endLocation,
                    start_time=previous.startTime,
                    duration_seconds=(
                        previous.durationSeconds
                        + segment.durationSeconds
                    ),
                    distance_meters=distance,
                    encoded_polyline=merge_polylines(
                        previous.encodedPolyline,
                        segment.encodedPolyline,
                    ),
                )
            )

        else:
            merged.append(segment)

    return merged


# coordinates driving, parking, drop-off, walking, and transit
# routing calls to construct a feasible multimodal journey
def compose_journey(
    origin: Location,
    destination: Location,
    parking_location: Location | None,
    boarding_location: Location,
    departure_time: datetime,
    requires_parking: bool = True,
) -> Journey | None:

    if departure_time.utcoffset() is None:
        raise ValueError("departure_time must be timezone-aware")

    departure_time = departure_time.astimezone(
        timezone.utc
    ).replace(microsecond=0)

    # Determine driving destination.
    if requires_parking:
        if parking_location is None:
            parking_location = boarding_location

        driving_destination = parking_location
    else:
        driving_destination = boarding_location

    # 1. Request driving routes.
    driving_result = get_routes(
        origin=origin,
        destination=driving_destination,
        mode=TravelMode.DRIVE,
        departure_time=departure_time,
    )

    for driving_route in driving_result.routes:
        drive_segment = make_route_segment(
            route=driving_route,
            kind="DRIVE",
            origin=origin,
            destination=driving_destination,
            start_time=departure_time,
        )

        if drive_segment is None:
            continue

        # 2. Construct parking or drop-off segment.
        stationary_segment = make_segment(
            kind="PARK" if requires_parking else "DROP_OFF",
            start_location=drive_segment.endLocation,
            end_location=drive_segment.endLocation,
            start_time=drive_segment.endTime,
            duration_seconds=(
                PARKING_DURATION_SECONDS
                if requires_parking
                else DROP_OFF_ACCESS_BUFFER_SECONDS
            ),
        )

        # 3. Generate walking options.
        walking_options = []

        if requires_parking and not locations_match(
            driving_destination,
            boarding_location,
            SEGMENT_CONTINUITY_TOLERANCE_METERS,
        ):
            walking_result = get_routes(
                origin=driving_destination,
                destination=boarding_location,
                mode=TravelMode.WALK,
            )

            for walking_route in walking_result.routes:
                walk_segment = make_route_segment(
                    route=walking_route,
                    kind="WALK",
                    origin=driving_destination,
                    destination=boarding_location,
                    start_time=stationary_segment.endTime,
                )

                if walk_segment is not None:
                    walking_options.append(walk_segment)

        else:
            # No separate walking segment required.
            walking_options.append(None)

        # 4. Request transit routes for each walking option.
        for walk_segment in walking_options:
            transit_departure_time = (
                walk_segment.endTime
                if walk_segment is not None
                else stationary_segment.endTime
            )

            transit_result = get_routes(
                origin=boarding_location,
                destination=destination,
                mode=TravelMode.TRANSIT,
                departure_time=transit_departure_time,
            )

            for transit_route in transit_result.routes:
                transit_segments = compose_transit_segments(
                    transit_route,
                    boarding_location,
                    destination,
                    transit_departure_time,
                )

                if not transit_segments:
                    continue

                # 5. Assemble the complete journey.
                segments = [drive_segment, stationary_segment]

                if walk_segment is not None:
                    segments.append(walk_segment)

                segments.extend(transit_segments)

                # Validate temporal continuity before merging.
                if any(
                    first.endTime != second.startTime
                    for first, second in zip(segments, segments[1:])
                ):
                    logger.debug(
                        "Rejecting journey: temporal discontinuity between segments"
                    )
                    continue

                # Validate geographical continuity before merging.
                if any(
                    not locations_match(
                        first.endLocation,
                        second.startLocation,
                        SEGMENT_CONTINUITY_TOLERANCE_METERS,
                    )
                    for first, second in zip(segments, segments[1:])
                ):
                    logger.debug(
                        "Rejecting journey: geographical discontinuity between segments"
                    )
                    continue

                segments = merge_walking_segments(segments)

                arrival_time = segments[-1].endTime

                transit_count = sum(
                    segment.kind == "TRANSIT"
                    for segment in segments
                )

                try:
                    return Journey(
                        id=str(uuid4()),
                        journeyType="DRIVE_WALK_TRANSIT",
                        segments=segments,
                        departureTime=departure_time,
                        arrivalTime=arrival_time,
                        totalDurationSeconds=int(
                            (arrival_time - departure_time).total_seconds()
                        ),
                        transferCount=max(0, transit_count - 1),
                    )
                except ValidationError as exc:
                    logger.warning(
                        "Rejecting journey due to validation error: %s",
                        exc,
                    )
                    continue

    return None
