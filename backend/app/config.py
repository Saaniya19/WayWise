import os

GOOGLE_ROUTE_MATRIX_URL = os.getenv(
    "GOOGLE_ROUTE_MATRIX_URL",
    "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix",
)

GOOGLE_ROUTES_URL = os.getenv(
    "GOOGLE_ROUTES_URL",
    "https://routes.googleapis.com/directions/v2:computeRoutes",
)

DROP_OFF_ACCESS_BUFFER_SECONDS = int(
    os.getenv("DROP_OFF_ACCESS_BUFFER_SECONDS", "60")
)

if DROP_OFF_ACCESS_BUFFER_SECONDS < 0:
    raise ValueError("Drop-off access buffer cannot be negative")