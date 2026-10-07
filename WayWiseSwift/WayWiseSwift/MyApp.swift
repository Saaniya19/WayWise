import SwiftUI
import GoogleMaps

@main
struct WayWiseApp: App {

    init() {
        GMSServices.provideAPIKey("INSERT_API_KEY")
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
