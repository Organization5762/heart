import SwiftUI
import PhotosUI                       // iOS 15+
import ImageIO
import MobileCoreServices

extension UIImage {
    /// Returns a 64×64 copy using Lanczos resampling.
    func resized(to side: CGFloat) -> UIImage {
        let renderer = UIGraphicsImageRenderer(size: .init(width: side, height: side))
        return renderer.image { _ in
            self.draw(in: CGRect(origin: .zero, size: renderer.format.bounds.size))
        }
    }
}

struct ContentView: View {
    @StateObject private var bleManager = BLEManager()
    @State private var statusMessage = ""
    @State private var textToSend = ""

    // Image-transfer state ---------------------------------------------
    @State private var pickerItem: PhotosPickerItem?
    @State private var resized64: UIImage?
    @State private var isSending = false

    // MARK: – Helpers ---------------------------------------------------
    private func send() {
        statusMessage = ""
        if let uiImg = resized64, let png = uiImg.pngData() {
            isSending = true
            bleManager.sendImage(png) { success in
                isSending = false
                statusMessage = success ? "Image sent!" : "Failed to send image"
            }
        } else {
            guard !textToSend.isEmpty else { return }
            let txt = textToSend
            isSending = true
            bleManager.sendText(txt) { success in
                isSending = false
                statusMessage = success ? "Text sent!" : "Failed to send text"
            }
        }
    }

    private func clearImage() {
        resized64 = nil
        pickerItem = nil
    }

    // MARK: – Body ------------------------------------------------------
    var body: some View {
        ScrollView {                // allow space on small screens
            VStack(spacing: 24) {
                Text("BLE iOS Client")
                    .font(.largeTitle)
                    .padding(.top)

                // TEXT --------------------------------------------------
                TextEditor(text: $textToSend)
                    .frame(height: 120)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(Color.secondary.opacity(0.4))
                    )
                    .padding(.horizontal)
                    .disabled(resized64 != nil)
                    .opacity(resized64 != nil ? 0.4 : 1)

                // IMAGE -------------------------------------------------
                if let uiImage = resized64 {
                    Image(uiImage: uiImage)
                        .interpolation(.none)
                        .resizable()
                        .frame(width: 128, height: 128)
                        .border(Color.gray)

                    Button("Clear Image", role: .destructive, action: clearImage)
                }

                PhotosPicker(selection: $pickerItem, matching: .images) {
                    Label("Choose Image", systemImage: "photo")
                }
                .disabled(!textToSend.isEmpty)       // mutual exclusion

                // SEND --------------------------------------------------
                Button("Send", action: send)
                    .buttonStyle(.borderedProminent)
                    .disabled((textToSend.isEmpty && resized64 == nil) || isSending)

                // STATUS ------------------------------------------------
                if isSending {
                    ProgressView("Sending…")
                } else if !statusMessage.isEmpty {
                    Text(statusMessage)
                        .foregroundColor(.primary)
                        .padding(.top, 2)
                }
            }
            .padding()
        }
        // IMAGE LOAD TASK ----------------------------------------------
        .task(id: pickerItem) {
            if let data = try? await pickerItem?.loadTransferable(type: Data.self),
               let img  = UIImage(data: data) {
                resized64 = img.resized(to: 64)
                textToSend = ""       // clear text so mutual exclusion holds
            }
        }
    }
}

func canonicalPNG(from img: UIImage) -> Data? {
    guard let cg = img.cgImage else { return nil }
    let data = NSMutableData()
    guard let dest = CGImageDestinationCreateWithData(data, kUTTypePNG, 1, nil) else { return nil }
    CGImageDestinationAddImage(dest, cg, nil)
    CGImageDestinationFinalize(dest)
    return data as Data
}
