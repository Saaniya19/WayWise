import SwiftUI

struct ContentView: View {
    var body: some View {
        GoogleMapView(
            apiKey: "AIzaSyAB-MaduXiNmQfmliW4wLzucOv-y5uP3_E"
        )
        .ignoresSafeArea()
    }
}

#Preview {
    ContentView()
}
