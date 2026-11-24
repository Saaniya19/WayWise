import SwiftUI
import GoogleMaps

@main
struct WayWiseApp: App {

    init() {
        GMSServices.provideAPIKey("AIzaSyAB-MaduXiNmQfmliW4wLzucOv-y5uP3_E")
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
