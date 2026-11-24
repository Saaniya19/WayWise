import Foundation
import CoreLocation

struct RoutesService {
    let apiKey: String

    func getDrivingRoute(
        from origin: CLLocationCoordinate2D,
        to destination: CLLocationCoordinate2D
    ) async throws -> RouteResult {

        let url = URL(
            string: "https://routes.googleapis.com/directions/v2:computeRoutes"
        )!

        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        request.setValue(
            "application/json",
            forHTTPHeaderField: "Content-Type"
        )

        request.setValue(
            apiKey,
            forHTTPHeaderField: "X-Goog-Api-Key"
        )

        request.setValue(
            "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline",
            forHTTPHeaderField: "X-Goog-FieldMask"
        )

        let body: [String: Any] = [
            "origin": [
                "location": [
                    "latLng": [
                        "latitude": origin.latitude,
                        "longitude": origin.longitude
                    ]
                ]
            ],
            "destination": [
                "location": [
                    "latLng": [
                        "latitude": destination.latitude,
                        "longitude": destination.longitude
                    ]
                ]
            ],
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_UNAWARE"
        ]

        request.httpBody = try JSONSerialization.data(
            withJSONObject: body
        )

        let (data, response) = try await URLSession.shared.data(
            for: request
        )

        guard let httpResponse = response as? HTTPURLResponse else {
            throw RoutesError.invalidResponse
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            let message = String(
                data: data,
                encoding: .utf8
            ) ?? "Unknown API error"

            throw RoutesError.apiError(message)
        }

        let decoded = try JSONDecoder().decode(
            RoutesResponse.self,
            from: data
        )

        guard let route = decoded.routes.first else {
            throw RoutesError.noRoutesFound
        }

        return RouteResult(
            distanceMeters: route.distanceMeters,
            duration: route.duration,
            encodedPolyline: route.polyline.encodedPolyline
        )
    }
}

private struct RoutesResponse: Decodable {
    let routes: [GoogleRoute]
}

private struct GoogleRoute: Decodable {
    let distanceMeters: Int
    let duration: String
    let polyline: GooglePolyline
}

private struct GooglePolyline: Decodable {
    let encodedPolyline: String
}

enum RoutesError: Error {
    case invalidResponse
    case noRoutesFound
    case apiError(String)
}
