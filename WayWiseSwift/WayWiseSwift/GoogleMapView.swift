//
//  GoogleMapView.swift
//  MyApp
//
import SwiftUI
import GoogleMaps
import CoreLocation

struct GoogleMapView: UIViewRepresentable {

    func makeUIView(context: Context) -> GMSMapView {

        // Start the map centered around University of Waterloo
        let camera = GMSCameraPosition.camera(
            withLatitude: 43.4723,
            longitude: -80.5449,
            zoom: 14.0
        )

        let options = GMSMapViewOptions()
        options.camera = camera

        let mapView = GMSMapView(options: options)

        // Create a marker
        let marker = GMSMarker()

        marker.position = CLLocationCoordinate2D(
            latitude: 43.4723,
            longitude: -80.5449
        )

        marker.title = "University of Waterloo"
        marker.snippet = "WayWise Google Maps SDK Test"

        // Add marker to the map
        marker.map = mapView

        return mapView
    }

    func updateUIView(_ uiView: GMSMapView, context: Context) {
        // Nothing needed here yet
    }
}

