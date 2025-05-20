//
//
//  Sends UTF-8 text messages to a Raspberry Pi peripheral advertising service 1235 /
//  characteristic 5679.  Each message is automatically null-terminated so the
//  peripheral can delimit them.
//
//  ─ Connection cycle ─
//  1. Caller invokes `sendText(_:completion:)`.
//  2. Manager scans, connects, discovers, writes payload in 20-byte chunks
//     using `.withoutResponse`, then disconnects.
//  3. Completion handler reports success (`true`) or failure (`false`).
//

import Foundation
import CoreBluetooth
import Combine

// Simple error wrapper for callers that care.
enum BLEError: Error {
    case bluetoothUnavailable
    case notReady               // no peripheral / characteristic yet
}

final class BLEManager: NSObject, ObservableObject {

    // MARK: – Observable state -------------------------------------------------

    /// Human-readable summary used by the UI.
    @Published private(set) var connectionState = "Disconnected"

    /// True once a secure bond (pairing) has been established.
    @Published private(set) var isPaired = false

    /// Rolling debug log presented in the SwiftUI debug pane.
    @Published private(set) var debugLogs: [String] = []

    // MARK: – Public API --------------------------------------------------

    /// Send plain text.  UTF-8 is enforced; completion `false` if encoding fails.
    func sendText(_ text: String, completion: ((Bool) -> Void)? = nil) {
        guard let data = text.data(using: .utf8) else {
            completion?(false)
            return
        }
        sendPayload(data, completion: completion)
    }

    /// Cancel any ongoing BLE connection/scan and reset internal state.
    func forgetAllConnections() {
        if let peripheral = targetPeripheral {
            centralManager.cancelPeripheralConnection(peripheral)
        }
        targetPeripheral      = nil
        writeCharacteristic   = nil
        pendingPayload        = nil
        onComplete            = nil

        log("🔄 Connections reset by user")
        connectionState = isPaired ? "Paired" : "Disconnected"
    }

    // MARK: – Private -----------------------------------------------------

    private let serviceUUID        = CBUUID(string: "1235")
    private let characteristicUUID = CBUUID(string: "5679")

    private var centralManager: CBCentralManager!
    private var targetPeripheral: CBPeripheral?
    private var writeCharacteristic: CBCharacteristic?

    private var pendingPayload: Data?
    private var onComplete: ((Bool) -> Void)?

    // Periodic pairing timer (fires every 5 s).
    private var pairingTimer: AnyCancellable?

    override init() {
        super.init()
        centralManager = CBCentralManager(delegate: self, queue: nil)

        // Fire every 5 seconds to attempt pairing until successful.
        pairingTimer = Timer.publish(every: 5.0, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.attemptPairing()
            }
    }

    // MARK: – Private helpers --------------------------------------------------

    private func log(_ message: String) {
        print(message)
        DispatchQueue.main.async {
            self.debugLogs.append(message)
            // Keep memory bounded – last 200 entries.
            if self.debugLogs.count > 200 {
                self.debugLogs.removeFirst(self.debugLogs.count - 200)
            }
        }
    }

    /// Stage a payload and kick off a fresh connection cycle.
    private func sendPayload(_ data: Data, completion: ((Bool) -> Void)?) {
        guard centralManager.state == .poweredOn else {
            completion?(false)
            return
        }

        // If we're already connected and have a valid characteristic, send directly
        if let peripheral = targetPeripheral, 
           peripheral.state == .connected,
           let characteristic = writeCharacteristic {
            log("🔗 Already connected - sending payload (\(data.count) bytes) directly")
            transmit(data, via: peripheral, characteristic: characteristic)
            onComplete = completion
            return
        }
        
        // Otherwise, start a new connection cycle
        connectionState = "Scanning"
        log("🔎 Starting scan to send payload (\(data.count) bytes)")

        // Reset state
        pendingPayload      = data
        onComplete          = completion
        writeCharacteristic = nil

        if let peripheral = targetPeripheral {
            centralManager.cancelPeripheralConnection(peripheral)
        }
        targetPeripheral = nil

        // Scan (with 3-second timeout so we don't wait forever).
        centralManager.scanForPeripherals(withServices: [serviceUUID], options: nil)
        DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) { [weak self] in
            guard let self, self.pendingPayload != nil, self.targetPeripheral == nil else { return }
            print("⏱ No peripheral found within timeout")
            self.log("⏱ No peripheral found within timeout")
            self.pendingPayload = nil
            self.onComplete?(false)
            self.onComplete = nil
            self.centralManager.stopScan()
        }
    }

    /// Break payload into 20-byte ATT packets and write them.
    private func transmit(_ data: Data,
                          via peripheral: CBPeripheral,
                          characteristic chr: CBCharacteristic)
    {
        let mtu = 20
        var offset = 0
        
        // Always append a null terminator so the peripheral knows where the message ends
        var terminatedData = data
        terminatedData.append(0x00)
        let finalData = terminatedData
        log("📝 Added null terminator to text payload")
        
        log("📤 Starting transmission: \(finalData.count) bytes")
        while offset < finalData.count {
            let chunk = finalData.subdata(in: offset ..< min(offset + mtu, finalData.count))
            peripheral.writeValue(chunk, for: chr, type: .withoutResponse)
            log("   Chunk \(offset/mtu + 1): \(chunk.count) bytes")
            offset += mtu
            usleep(10_000)  // Increase to 10ms pause to avoid congestion
        }
        log("✅ Sent \(finalData.count) bytes in \(Int(ceil(Double(finalData.count) / Double(mtu)))) packets")

        connectionState = "Waiting for flush"

        // Mark payload as consumed so that, should the connection fail and
        // reconnect, we don't send the same data again.
        pendingPayload = nil

        // Give the BLE stack enough time to flush the transmit queue before we
        // sever the link.
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [weak self] in
            guard let self else { return }
            self.log("🔌 Disconnecting after successful transmission")
            self.centralManager.cancelPeripheralConnection(peripheral)
        }
    }

    /// Attempt a lightweight write to trigger pairing if not yet paired.
    private func attemptPairing() {
        guard !isPaired,
              centralManager.state == .poweredOn,
              pendingPayload == nil,
              targetPeripheral == nil else { return }

        // Start a lightweight connection cycle with *no* payload – when the
        // characteristic is discovered we will send a 1-byte ping with
        // `.withResponse` to trigger the OS pairing prompt.

        // Reset state similar to `sendPayload` but without staging data.
        pendingPayload      = nil
        onComplete          = nil

        if let peripheral = targetPeripheral {
            centralManager.cancelPeripheralConnection(peripheral)
        }
        targetPeripheral = nil

        connectionState = "Scanning"
        centralManager.scanForPeripherals(withServices: [serviceUUID], options: nil)
    }
}


// MARK: – CBCentralManagerDelegate + CBPeripheralDelegate ---------------

extension BLEManager: CBCentralManagerDelegate, CBPeripheralDelegate {

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        guard central.state == .poweredOn else {
            log("⚠️  Bluetooth unavailable: \(central.state.rawValue)")
            connectionState = "Bluetooth Off"
            return
        }
        // If a payload is waiting and we aren't yet scanning/connected, start.
        if pendingPayload != nil && targetPeripheral == nil {
            central.scanForPeripherals(withServices: [serviceUUID], options: nil)
        }
    }

    func centralManager(_ central: CBCentralManager,
                        didDiscover peripheral: CBPeripheral,
                        advertisementData: [String : Any],
                        rssi RSSI: NSNumber)
    {
        log("🔍 Discovered \(peripheral.name ?? "unknown") (RSSI \(RSSI))")
        connectionState = "Connecting"
        targetPeripheral = peripheral
        peripheral.delegate = self
        central.stopScan()
        central.connect(peripheral, options: nil)
    }

    func centralManager(_ central: CBCentralManager,
                        didConnect peripheral: CBPeripheral)
    {
        log("🔗 Connected to \(peripheral.name ?? "device")")
        connectionState = "Discovering"
        peripheral.discoverServices([serviceUUID])
    }

        func centralManager(_ central: CBCentralManager,
                        didFailToConnect peripheral: CBPeripheral,
                        error: Error?)
    {
        log("⚠️  Failed to connect: \(error?.localizedDescription ?? "unknown")")
        connectionState = isPaired ? "Paired" : "Disconnected"

        // ── Clean-up & notify caller so the UI can leave the “Sending…” state ──
        targetPeripheral      = nil
        writeCharacteristic   = nil
        pendingPayload        = nil

        onComplete?(false)      // tell ContentView that the send failed
        onComplete = nil
    }

    func peripheral(_ peripheral: CBPeripheral,
                    didDiscoverServices error: Error?)
    {
        for service in peripheral.services ?? [] where service.uuid == serviceUUID {
            peripheral.discoverCharacteristics([characteristicUUID], for: service)
        }
    }

    func peripheral(_ peripheral: CBPeripheral,
                    didDiscoverCharacteristicsFor service: CBService,
                    error: Error?)
    {
        guard let chr = service.characteristics?.first(where: { $0.uuid == characteristicUUID }) else { return }

        // No payload ≙ this is the periodic pairing ping.
        if pendingPayload == nil {
            connectionState = "Pairing"
            let ping = Data([0x00])
            peripheral.writeValue(ping, for: chr, type: .withResponse)
            return
        }

        guard let payload = pendingPayload else { return }

        connectionState = "Transmitting"
        writeCharacteristic = chr
        transmit(payload, via: peripheral, characteristic: chr)
    }

    func peripheral(_ peripheral: CBPeripheral,
                    didWriteValueFor characteristic: CBCharacteristic,
                    error: Error?) {

        if error == nil {
            isPaired = true
            connectionState = "Paired"
            log("🔒 Pairing successful – secure link established")
        } else if let err = error {
            // Check for authentication/encryption failures that indicate
            // the devices are not yet bonded.
            let nsErr = err as NSError
            if nsErr.domain == CBATTErrorDomain,
               nsErr.code == CBATTError.insufficientAuthentication.rawValue || nsErr.code == CBATTError.insufficientEncryption.rawValue {
                isPaired = false
                connectionState = "Not Paired"
                log("🔓 Pairing failed – will retry")
            }
        }

        // If we initiated only a pairing ping, terminate link right away.
        if pendingPayload == nil {
            centralManager.cancelPeripheralConnection(peripheral)
        }
    }

    func centralManager(_ central: CBCentralManager,
                        didDisconnectPeripheral peripheral: CBPeripheral,
                        error: Error?)
    {
        let clean = (error == nil)
        if clean {
            log("🔌 Disconnected from \(peripheral.name ?? "device")")
        } else {
            log("⚠️  Disconnect error: \(error!.localizedDescription)")
        }

        targetPeripheral      = nil
        writeCharacteristic   = nil
        pendingPayload        = nil

        onComplete?(clean)
        onComplete = nil

        // Reflect final state.
        connectionState = isPaired ? "Paired" : "Disconnected"
    }
}
