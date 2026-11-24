import Foundation

struct RouteResult: Decodable {
    let distanceMeters: Int
    let duration: String
    let encodedPolyline: String
}
