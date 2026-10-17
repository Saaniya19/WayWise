import SwiftUI
import GoogleMaps
import CoreLocation

struct GoogleMapView: UIViewRepresentable {

    let apiKey: String

    // University of Waterloo
    private let origin = CLLocationCoordinate2D(
        latitude: 43.4723,
        longitude: -80.5449
    )

    // Conestoga Mall
    private let destination = CLLocationCoordinate2D(
        latitude: 43.4977,
        longitude: -80.5273
    )


    func makeUIView(context: Context) -> GMSMapView {

        // MARK: Camera

        let camera = GMSCameraPosition.camera(
            withLatitude: 43.485,
            longitude: -80.536,
            zoom: 12.5
        )

        let options = GMSMapViewOptions()
        options.camera = camera

        let mapView = GMSMapView(options: options)


        // MARK: Origin Marker

        let originMarker = GMSMarker()

        originMarker.position = origin
        originMarker.title = "University of Waterloo"
        originMarker.snippet = "Origin"

        originMarker.map = mapView


        // MARK: Destination Marker

        let destinationMarker = GMSMarker()

        destinationMarker.position = destination
        destinationMarker.title = "Conestoga Mall"
        destinationMarker.snippet = "Destination"

        destinationMarker.map = mapView


        // MARK: Request Real Route

        Task {

            let service = RoutesService(
                apiKey: apiKey
            )

            do {

                let route = try await service.getDrivingRoute(
                    from: origin,
                    to: destination
                )

                print("Route received!")
                print("Distance: \(route.distanceMeters) meters")
                print("Duration: \(route.duration)")

                await MainActor.run {

                    drawRoute(
                        route,
                        on: mapView
                    )

                }

            } catch {

                print("Failed to get route:")
                print(error)

            }
        }

        return mapView
    }


    func updateUIView(
        _ uiView: GMSMapView,
        context: Context
    ) {

    }


    // MARK: - Draw Route

    private func drawRoute(
        _ route: RouteResult,
        on mapView: GMSMapView
    ) {

        guard let path = GMSPath(
            fromEncodedPath: route.encodedPolyline
        ) else {

            print("Could not decode route polyline.")
            return
        }

        let polyline = GMSPolyline(path: path)

        polyline.strokeWidth = 6

        polyline.map = mapView


        // Automatically zoom so entire route is visible

        let bounds = GMSCoordinateBounds(path: path)

        let cameraUpdate = GMSCameraUpdate.fit(
            bounds,
            withPadding: 60
        )

        mapView.animate(
            with: cameraUpdate
        )
    }
}
