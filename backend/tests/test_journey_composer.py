from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.models.common import Location
from app.models.routing import (
    Route,
    RouteResult,
    Leg,
    Segment,
    TravelMode,
    TransitDetails,
    TransitStop,
)
from app.services.journey_composer import compose_journey

import polyline
from app.services.journey_composer import merge_polylines


DEPARTURE_TIME = datetime(
    2026, 11, 24, 8, 0, tzinfo=timezone.utc
)

ORIGIN = Location(
    name="University of Waterloo",
    latitude=43.4723,
    longitude=-80.5449,
)

PARKING = Location(
    name="Kitchener GO Parking",
    latitude=43.4550,
    longitude=-80.4790,
)

BOARDING = Location(
    name="Kitchener GO Station",
    latitude=43.4555,
    longitude=-80.4785,
)

ALIGHTING = Location(
    latitude=43.6453,
    longitude=-79.3806,
)

DESTINATION = Location(
    name="CN Tower",
    latitude=43.6426,
    longitude=-79.3871,
)


def time_at(minutes):
    return DEPARTURE_TIME + timedelta(minutes=minutes)


@pytest.fixture
def driving_route():
    return Route(
        duration_seconds=1800,
        distance_meters=20000,
        start_location=ORIGIN,
        end_location=PARKING,
    )


@pytest.fixture
def walking_route():
    return Route(
        duration_seconds=480,
        distance_meters=600,
        start_location=PARKING,
        end_location=BOARDING,
    )


@pytest.fixture
def transit_route():
    return Route(
        duration_seconds=2700,
        distance_meters=70000,
        start_location=BOARDING,
        end_location=DESTINATION,
        legs=[
            Leg(
                segments=[
                    Segment(
                        mode=TravelMode.TRANSIT,
                        duration_seconds=1800,
                        distance_meters=69300,
                        start_location=BOARDING,
                        end_location=ALIGHTING,
                        transit_details=TransitDetails(
                            departure_stop=TransitStop(
                                name="Kitchener GO",
                                location=BOARDING,
                            ),
                            arrival_stop=TransitStop(
                                name="Union Station",
                                location=ALIGHTING,
                            ),
                            departure_time=time_at(45),
                            arrival_time=time_at(75),
                            line_name="Kitchener",
                            agency_name="GO Transit",
                            vehicle_type="TRAIN",
                            route_short_name="KI",
                            headsign="Union Station",
                            stop_count=8,
                        ),
                    ),
                    Segment(
                        mode=TravelMode.WALK,
                        duration_seconds=600,
                        distance_meters=700,
                        start_location=ALIGHTING,
                        end_location=DESTINATION,
                    ),
                ]
            )
        ],
    )
    

def run_composer(
    driving_routes,
    walking_routes,
    transit_routes,
    departure_time=DEPARTURE_TIME,
):
    with patch(
        "app.services.journey_composer.get_routes"
    ) as mock_get_routes:

        responses = {
            TravelMode.DRIVE: RouteResult(
                routes=driving_routes
            ),
            TravelMode.WALK: RouteResult(
                routes=walking_routes
            ),
            TravelMode.TRANSIT: RouteResult(
                routes=transit_routes
            ),
        }

        def mock_routes(*args, **kwargs):
            return responses[kwargs["mode"]]

        mock_get_routes.side_effect = mock_routes

        journey = compose_journey(
            origin=ORIGIN,
            destination=DESTINATION,
            parking_location=PARKING,
            boarding_location=BOARDING,
            departure_time=departure_time,
        )

        return journey, mock_get_routes

def test_successful_journey(
    driving_route,
    walking_route,
    transit_route,
):
    journey, mock = run_composer(
        [driving_route],
        [walking_route],
        [transit_route],
    )

    assert journey is not None

    assert journey.journeyType == "DRIVE_WALK_TRANSIT"

    assert [s.kind for s in journey.segments] == [
        "DRIVE",
        "PARK",
        "WALK",
        "WAIT",
        "TRANSIT",
        "WALK",
    ]

    assert journey.segments[0].startLocation == ORIGIN
    assert journey.segments[-1].endLocation == DESTINATION

    assert journey.departureTime == DEPARTURE_TIME
    assert journey.arrivalTime == time_at(85)

    assert journey.totalDurationSeconds == 5100
    assert journey.transferCount == 0

    assert mock.call_count == 3
    

def test_transit_details_propagation(
    driving_route,
    walking_route,
    transit_route,
):
    journey, _ = run_composer(
        [driving_route],
        [walking_route],
        [transit_route],
    )

    assert journey is not None

    transit = next(
        s for s in journey.segments
        if s.kind == "TRANSIT"
    )

    details = transit.transitDetails

    assert details is not None
    assert details.agencyName == "GO Transit"
    assert details.serviceName == "Kitchener"
    assert details.vehicleType == "TRAIN"
    assert details.routeShortName == "KI"
    assert details.headsign == "Union Station"
    assert details.stopCount == 8
    assert details.timingBasis == "SCHEDULED"

    
def test_parking_duration(
    driving_route,
    walking_route,
    transit_route,
):
    journey, _ = run_composer(
        [driving_route],
        [walking_route],
        [transit_route],
    )

    assert journey is not None

    parking = journey.segments[1]

    assert parking.kind == "PARK"
    assert parking.durationSeconds == 120
    assert parking.startTime == time_at(30)
    assert parking.endTime == time_at(32)

    assert parking.startLocation == PARKING
    assert parking.endLocation == PARKING
    assert parking.distanceMeters is None


def test_waiting_duration(
    driving_route,
    walking_route,
    transit_route,
):
    journey, _ = run_composer(
        [driving_route],
        [walking_route],
        [transit_route],
    )

    assert journey is not None

    waiting = journey.segments[3]

    assert waiting.kind == "WAIT"
    assert waiting.durationSeconds == 300
    assert waiting.startTime == time_at(40)
    assert waiting.endTime == time_at(45)
    assert waiting.distanceMeters is None


def test_merge_polylines():
    first_points = [
        (43.450, -80.480),
        (43.451, -80.481),
    ]

    second_points = [
        (43.451, -80.481),
        (43.452, -80.482),
    ]

    result = merge_polylines(
        polyline.encode(first_points),
        polyline.encode(second_points),
    )

    assert result is not None
    assert polyline.decode(result) == [
        (43.450, -80.480),
        (43.451, -80.481),
        (43.452, -80.482),
    ]


def test_merge_polylines_missing_geometry():
    encoded = polyline.encode([(43.450, -80.480)])

    assert merge_polylines(None, encoded) is None
    assert merge_polylines(encoded, None) is None
    assert merge_polylines(None, None) is None


def test_chronological_consistency(
    driving_route,
    walking_route,
    transit_route,
):
    journey, _ = run_composer(
        [driving_route],
        [walking_route],
        [transit_route],
    )

    assert journey is not None

    for segment in journey.segments:
        assert segment.startTime.utcoffset() is not None
        assert segment.endTime.utcoffset() is not None

        assert segment.endTime >= segment.startTime

        assert segment.durationSeconds == (
            segment.endTime - segment.startTime
        ).total_seconds()

    for previous, current in zip(
        journey.segments,
        journey.segments[1:],
    ):
        assert previous.endTime == current.startTime

    assert journey.totalDurationSeconds == sum(
        segment.durationSeconds
        for segment in journey.segments
    )

    assert journey.totalDurationSeconds == (
        journey.arrivalTime - journey.departureTime
    ).total_seconds()


def test_transit_request_departure_time(
    driving_route,
    walking_route,
    transit_route,
):
    journey, mock = run_composer(
        [driving_route],
        [walking_route],
        [transit_route],
    )

    assert journey is not None

    transit_call = next(
        call for call in mock.call_args_list
        if call.kwargs["mode"] == TravelMode.TRANSIT
    )

    # 30 minutes driving + 2 minutes parking
    # + 8 minutes walking = 40 minutes.
    assert transit_call.kwargs["departure_time"] == (
        time_at(40)
    )

    assert transit_call.kwargs["origin"] == BOARDING
    assert transit_call.kwargs["destination"] == DESTINATION
    

@pytest.mark.parametrize(
    "train_departure, expected_feasible",
    [
        (35, False),
        (39, False),
        (40, True),
        (41, True),
        (45, True),
    ],
)
def test_train_feasibility(
    driving_route,
    walking_route,
    transit_route,
    train_departure,
    expected_feasible,
):
    details = (
        transit_route.legs[0]
        .segments[0]
        .transit_details
    )

    details.departure_time = time_at(train_departure)
    details.arrival_time = time_at(train_departure + 30)

    journey, _ = run_composer(
        [driving_route],
        [walking_route],
        [transit_route],
    )

    if expected_feasible:
        assert journey is not None

        transit = next(
            s for s in journey.segments
            if s.kind == "TRANSIT"
        )

        assert transit.startTime == time_at(
            train_departure
        )

        assert journey.totalDurationSeconds == (
            train_departure + 40
        ) * 60

    else:
        assert journey is None


@pytest.mark.parametrize(
    "second_departure, expected_feasible",
    [
        (74, False),
        (75, True),
        (80, True),
    ],
)
def test_intermediate_connection(
    driving_route,
    walking_route,
    transit_route,
    second_departure,
    expected_feasible,
):
    second_ride = Segment(
        mode=TravelMode.TRANSIT,
        duration_seconds=600,
        distance_meters=2000,
        start_location=ALIGHTING,
        end_location=DESTINATION,
        transit_details=TransitDetails(
            departure_stop=TransitStop(
                location=ALIGHTING,
            ),
            arrival_stop=TransitStop(
                location=DESTINATION,
            ),
            departure_time=time_at(second_departure),
            arrival_time=time_at(second_departure + 10),
            agency_name="TTC",
            vehicle_type="BUS",
        ),
    )

    # Replace the final walking segment with a bus ride.
    transit_route.legs[0].segments[1] = second_ride

    journey, _ = run_composer(
        [driving_route],
        [walking_route],
        [transit_route],
    )

    if expected_feasible:
        assert journey is not None
        assert journey.transferCount == 1

        transit_segments = [
            s for s in journey.segments
            if s.kind == "TRANSIT"
        ]

        assert len(transit_segments) == 2

    else:
        assert journey is None
        

@pytest.mark.parametrize(
    "unavailable_mode",
    [
        TravelMode.DRIVE,
        TravelMode.WALK,
        TravelMode.TRANSIT,
    ],
)
def test_no_available_route(
    driving_route,
    walking_route,
    transit_route,
    unavailable_mode,
):
    journey, _ = run_composer(
        [] if unavailable_mode == TravelMode.DRIVE
        else [driving_route],

        [] if unavailable_mode == TravelMode.WALK
        else [walking_route],

        [] if unavailable_mode == TravelMode.TRANSIT
        else [transit_route],
    )

    assert journey is None
    

@pytest.mark.parametrize(
    "missing_field",
    [
        "duration_seconds",
        "distance_meters",
        "start_location",
        "end_location",
    ],
)
def test_missing_driving_data(
    driving_route,
    walking_route,
    transit_route,
    missing_field,
):
    setattr(driving_route, missing_field, None)

    journey, _ = run_composer(
        [driving_route],
        [walking_route],
        [transit_route],
    )

    assert journey is None


@pytest.mark.parametrize(
    "missing_field",
    [
        "departure_time",
        "arrival_time",
        "departure_stop",
        "arrival_stop",
    ],
)
def test_missing_transit_data(
    driving_route,
    walking_route,
    transit_route,
    missing_field,
):
    details = (
        transit_route.legs[0]
        .segments[0]
        .transit_details
    )

    setattr(details, missing_field, None)

    journey, _ = run_composer(
        [driving_route],
        [walking_route],
        [transit_route],
    )

    assert journey is None
    

def test_disconnected_driving_route(
    driving_route,
    walking_route,
    transit_route,
):
    driving_route.end_location = Location(
        latitude=44.0,
        longitude=-79.0,
    )

    journey, _ = run_composer(
        [driving_route],
        [walking_route],
        [transit_route],
    )

    assert journey is None


def test_disconnected_transit_route(
    driving_route,
    walking_route,
    transit_route,
):
    transit_route.legs[0].segments[
        1
    ].start_location = Location(
        latitude=44.0,
        longitude=-79.0,
    )

    journey, _ = run_composer(
        [driving_route],
        [walking_route],
        [transit_route],
    )

    assert journey is None
    

def test_merge_consecutive_walking_segments(
    driving_route,
    walking_route,
    transit_route,
):
    extra_walk = Segment(
        mode=TravelMode.WALK,
        duration_seconds=60,
        distance_meters=50,
        start_location=BOARDING,
        end_location=BOARDING,
    )

    transit_route.legs[0].segments.insert(
        0, extra_walk
    )

    journey, _ = run_composer(
        [driving_route],
        [walking_route],
        [transit_route],
    )

    assert journey is not None

    walking = journey.segments[2]

    assert walking.kind == "WALK"
    assert walking.durationSeconds == 540
    assert walking.distanceMeters == 650

    waiting = journey.segments[3]

    assert waiting.kind == "WAIT"
    assert waiting.durationSeconds == 240

    for previous, current in zip(
        journey.segments,
        journey.segments[1:],
    ):
        assert not (
            previous.kind == "WALK"
            and current.kind == "WALK"
        )

    assert journey.totalDurationSeconds == 5100
    

def test_alternative_transit_route(
    driving_route,
    walking_route,
    transit_route,
):
    missed_route = transit_route.model_copy(deep=True)

    missed_details = (
        missed_route.legs[0]
        .segments[0]
        .transit_details
    )

    missed_details.departure_time = time_at(35)
    missed_details.arrival_time = time_at(65)

    journey, _ = run_composer(
        [driving_route],
        [walking_route],
        [missed_route, transit_route],
    )

    assert journey is not None

    transit = next(
        s for s in journey.segments
        if s.kind == "TRANSIT"
    )

    assert transit.startTime == time_at(45)
    


