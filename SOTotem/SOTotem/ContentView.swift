import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var bleManager: BLEManager
    @State private var statusMessage = ""
    @State private var textToSend = ""
    @State private var showDebugLog = false
    @State private var isSending = false

    // MARK: – Helpers ---------------------------------------------------
    private func send() {
        statusMessage = ""
        guard !textToSend.isEmpty else { return }
        let txt = textToSend
        isSending = true
        bleManager.sendText(txt) { success in
            isSending = false
            statusMessage = success ? "Text sent!" : "Failed to send text"
            if success {
                textToSend = ""   // clear after successful send
            }
        }
    }

    // MARK: – Body ------------------------------------------------------
    var body: some View {
        ScrollView {                // allow space on small screens
            VStack(spacing: 24) {
                Text("BLE iOS Client")
                    .font(.largeTitle)
                    .padding(.top)
                
                // Connection status
                HStack {
                    Text("Status:")
                    Text(bleManager.connectionState)
                        .foregroundColor(connectionStateColor(bleManager.connectionState))
                        .bold()
                }

                // TEXT --------------------------------------------------
                TextEditor(text: $textToSend)
                    .frame(height: 120)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(Color.secondary.opacity(0.4))
                    )
                    .padding(.horizontal)
                    .disabled(isSending)

                // SEND --------------------------------------------------
                Button("Send", action: send)
                    .buttonStyle(.borderedProminent)
                    .disabled(textToSend.isEmpty || isSending)

                // STATUS ------------------------------------------------
                if isSending {
                    ProgressView("Sending…")
                } else if !statusMessage.isEmpty {
                    Text(statusMessage)
                        .foregroundColor(.primary)
                        .padding(.top, 2)
                }
                
                // Add reset button for connection issues
                Button(action: {
                    bleManager.forgetAllConnections()
                    statusMessage = "Connections reset"
                }) {
                    Label("Reset Connections", systemImage: "arrow.triangle.2.circlepath")
                }
                .font(.footnote)
                .padding(.top, 8)
                .buttonStyle(.bordered)
                .foregroundColor(.red)
                .opacity(0.8)
                
                // Debug logs toggle
                Button(action: {
                    showDebugLog.toggle()
                }) {
                    Label(showDebugLog ? "Hide Debug Log" : "Show Debug Log", 
                          systemImage: showDebugLog ? "chevron.up" : "chevron.down")
                }
                .font(.footnote)
                .padding(.top, 4)
                
                // Debug log view
                if showDebugLog {
                    VStack(alignment: .leading, spacing: 2) {
                        ForEach(bleManager.debugLogs.suffix(10), id: \.self) { log in
                            Text(log)
                                .font(.system(size: 10, design: .monospaced))
                                .lineLimit(2)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .padding(8)
                    .background(Color.black.opacity(0.05))
                    .cornerRadius(8)
                }
            }
            .padding()
        }
    }
    
    // Helper to provide color based on connection state
    private func connectionStateColor(_ state: String) -> Color {
        switch state {
        case "Connected", "Transmitting", "Paired":
            return .green
        case "Scanning", "Connecting", "Discovering", "Waiting for flush", "Pairing":
            return .orange
        case "Disconnected", "Bluetooth Off":
            return .red
        default:
            return .gray
        }
    }
}
