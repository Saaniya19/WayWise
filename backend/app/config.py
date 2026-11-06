import os

GOOGLE_ROUTES_URL = os.getenv(
    "GOOGLE_ROUTES_URL",
    "https://routes.googleapis.com/directions/v2:computeRoutes",
)
