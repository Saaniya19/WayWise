from datetime import datetime, timedelta, timezone
from math import radians, sin, cos, asin, sqrt
from uuid import uuid4

from app.models.common import Location
from app.models.journey import (
    Journey,
    JourneySegment,
    TransitDetails,
)
from app.models.routing import Route, TravelMode
from app.services.google_routes_client import get_routes
from app.services.timing_service import checkConnection


PARKING_DURATION_SECONDS = 120
LOCATION_TOLERANCE_METERS = 100


def locations_match(
    first: Location,
    second: Location,
) -> bool:
    lat1 = radians(first.latitude)
    lat2 = radians(second.latitude)

    dlat = lat2 - lat1
    dlon = radians(second.longitude - first.longitude)

    a = (
        sin(dlat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    )

    distance = 2 * 6371000 * asin(sqrt(min(1.0, a)))

    return distance <= LOCATION_TOLERANCE_METERS
    

def make_segment(
    kind,
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
        origin, route.start_location
    ):
        return None

    if not locations_match(
        destination, route.end_location
    ):
        return None

    return make_segment(
        kind=kind,
        start_location=origin,
        end_location=destination,
        start_time=start_time,
        duration_seconds=route.duration_seconds,
        distance_meters=route.distance_meters,
        encoded_polyline=route.encoded_polyline,
    )

    
def compose_transit_segments(
    route: Route,
    boarding_location: Location,
    destination: Location,
    start_time: datetime,
) -> list[JourneySegment] | None:

    segments = []
    current_time = start_time
    current_location = boarding_location
    transit_count = 0

    for leg in route.legs:
        for step in leg.segments:

            if step.mode == TravelMode.WALK:

                if (
                    step.duration_seconds is None
                    or step.duration_seconds < 0
                    or step.distance_meters is None
                    or step.start_location is None
                    or step.end_location is None
                ):
                    return None

                if not locations_match(
                    current_location,
                    step.start_location,
                ):
                    return None

                segment = make_segment(
                    kind="WALK",
                    start_location=current_location,
                    end_location=step.end_location,
                    start_time=current_time,
                    duration_seconds=step.duration_seconds,
                    distance_meters=step.distance_meters,
                    encoded_polyline=step.encoded_polyline,
                )

            elif step.mode == TravelMode.TRANSIT:

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
                    return None

                if (
                    details.departure_time.utcoffset() is None
                    or details.arrival_time.utcoffset() is None
                ):
                    return None

                departure = details.departure_time.astimezone(
                    timezone.utc
                )
                arrival = details.arrival_time.astimezone(
                    timezone.utc
                )

                if arrival <= departure:
                    return None

                boarding_stop = details.departure_stop.location
                alighting_stop = details.arrival_stop.location

                if not locations_match(
                    current_location, boarding_stop
                ):
                    return None

                connection = checkConnection(
                    current_time,
                    departure,
                    minBufferSeconds=0,
                )

                # The traveller has missed this service.
                if not connection.isFeasible:
                    return None

                wait_seconds = (
                    departure - current_time
                ).total_seconds()

                ride_seconds = (
                    arrival - departure
                ).total_seconds()

                if (
                    not wait_seconds.is_integer()
                    or not ride_seconds.is_integer()
                ):
                    return None

                # Include time spent waiting for transit.
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
                    routeShortName=None,
                    vehicleType=details.vehicle_type,
                    boardingStop=boarding_stop,
                    alightingStop=alighting_stop,
                    headsign=None,
                    stopCount=None,
                    timingBasis="SCHEDULED",
                )

                segment = make_segment(
                    kind="TRANSIT",
                    start_location=boarding_stop,
                    end_location=alighting_stop,
                    start_time=departure,
                    duration_seconds=int(ride_seconds),
                    distance_meters=step.distance_meters,
                    encoded_polyline=step.encoded_polyline,
                    transit_details=transit_details,
                )

                transit_count += 1

            else:
                return None

            segments.append(segment)
            current_time = segment.endTime
            current_location = segment.endLocation

    if transit_count == 0:
        return None

    if not locations_match(current_location, destination):
        return None

    return segments
    

def merge_walking_segments(
    segments: list[JourneySegment],
) -> list[JourneySegment]:

    merged = []

    for segment in segments:

        if (
            merged
            and merged[-1].kind == "WALK"
            and segment.kind == "WALK"
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
                )
            )

        else:
            merged.append(segment)

    return merged


def compose_journey(
    origin: Location,
    destination: Location,
    parking_location: Location,
    boarding_location: Location,
    departure_time: datetime,
) -> Journey | None:

    if departure_time.utcoffset() is None:
        raise ValueError(
            "departure_time must be timezone-aware"
        )

    departure_time = departure_time.astimezone(
        timezone.utc
    ).replace(microsecond=0)

    # 1. Drive from origin to parking.
    driving_result = get_routes(
        origin=origin,
        destination=parking_location,
        mode=TravelMode.DRIVE,
        departure_time=departure_time,
    )

    for driving_route in driving_result.routes:

        driving_segment = make_route_segment(
            route=driving_route,
            kind="DRIVE",
            origin=origin,
            destination=parking_location,
            start_time=departure_time,
        )

        if driving_segment is None:
            continue

        # 2. Allot two minutes for parking.
        parking_segment = make_segment(
            kind="PARK",
            start_location=parking_location,
            end_location=parking_location,
            start_time=driving_segment.endTime,
            duration_seconds=PARKING_DURATION_SECONDS,
        )

        # 3. Walk from parking to the transit station.
        walking_result = get_routes(
            origin=parking_location,
            destination=boarding_location,
            mode=TravelMode.WALK,
        )

        for walking_route in walking_result.routes:

            walking_segment = make_route_segment(
                route=walking_route,
                kind="WALK",
                origin=parking_location,
                destination=boarding_location,
                start_time=parking_segment.endTime,
            )

            if walking_segment is None:
                continue

            # 4. Request transit routes based on when
            # the traveller actually reaches the station.
            transit_result = get_routes(
                origin=boarding_location,
                destination=destination,
                mode=TravelMode.TRANSIT,
                departure_time=walking_segment.endTime,
            )

            for transit_route in transit_result.routes:

                transit_segments = compose_transit_segments(
                    route=transit_route,
                    boarding_location=boarding_location,
                    destination=destination,
                    start_time=walking_segment.endTime,
                )

                if transit_segments is None:
                    continue

                # 5. Compose the complete journey.
                segments = merge_walking_segments([
                    driving_segment,
                    parking_segment,
                    walking_segment,
                    *transit_segments,
                ])

                # Validate geographical continuity.
                if any(
                    not locations_match(
                        previous.endLocation,
                        current.startLocation,
                    )
                    for previous, current in zip(
                        segments, segments[1:]
                    )
                ):
                    continue

                arrival_time = segments[-1].endTime

                transit_count = sum(
                    segment.kind == "TRANSIT"
                    for segment in segments
                )

                return Journey(
                    id=str(uuid4()),
                    journeyType="DRIVE_WALK_TRANSIT",
                    segments=segments,
                    departureTime=departure_time,
                    arrivalTime=arrival_time,
                    totalDurationSeconds=int(
                        (
                            arrival_time - departure_time
                        ).total_seconds()
                    ),
                    transferCount=max(
                        0, transit_count - 1
                    ),
                )

    # No feasible journey was found.
    return None

