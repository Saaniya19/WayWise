import os

GOOGLE_ROUTES_URL = os.getenv(
    "GOOGLE_ROUTES_URL",
    "https://routes.googleapis.com/directions/v2:computeRoutes",
)


DROP_OFF_ACCESS_BUFFER_SECONDS = int(
    os.getenv("DROP_OFF_ACCESS_BUFFER_SECONDS", "60")
)

if DROP_OFF_ACCESS_BUFFER_SECONDS < 0:
    raise ValueError("Drop-off access buffer cannot be negative")


LOCATION_TOLERANCE_METERS = int(
    os.getenv("LOCATION_TOLERANCE_METERS", "100")
)


PARKING_DURATION_SECONDS = int(
    os.getenv("PARKING_DURATION_SECONDS", "120")
)
