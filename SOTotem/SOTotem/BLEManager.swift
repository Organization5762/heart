//
//  BLEManager.swift
//  SOTotem
//
//  Re-written 2025-05-20
//
//  Sends either UTF-8 text *or* arbitrary binary payloads (e.g. 64 × 64 PNGs)
//  to a Raspberry Pi peripheral advertising service 1234 / characteristic 5678.
//
//  ─ Connection cycle ─
//  1. Caller invokes `sendText(_:completion:)` or `sendImage(_:completion:)`.
//  2. Manager scans, connects, discovers, writes payload in 20-byte chunks
//     using `.withoutResponse`, then disconnects.
//  3. Completion handler reports success (`true`) or failure (`false`).
//

import Foundation
import CoreBluetooth

// Simple error wrapper for callers that care.
enum BLEError: Error {
    case bluetoothUnavailable
    case notReady               // no peripheral / characteristic yet
}

final class BLEManager: NSObject, ObservableObject {

    // MARK: – Public API --------------------------------------------------

    /// Send plain text.  UTF-8 is enforced; completion `false` if encoding fails.
    func sendText(_ text: String, completion: ((Bool) -> Void)? = nil) {
        guard let data = text.data(using: .utf8) else {
            completion?(false)
            return
        }
        // Add a null terminator to mark the end of text
        var textWithTerminator = data
        textWithTerminator.append(0) // Null terminator
        sendPayload(textWithTerminator, completion: completion)
    }

    /// Send an entire PNG (or any binary) as Data.
    func sendImage(_ png: Data, completion: ((Bool) -> Void)? = nil) {
        sendPayload(png, completion: completion)
    }


    // MARK: – Private -----------------------------------------------------

    private let serviceUUID        = CBUUID(string: "1234")
    private let characteristicUUID = CBUUID(string: "5678")

    private var centralManager: CBCentralManager!
    private var targetPeripheral: CBPeripheral?
    private var writeCharacteristic: CBCharacteristic?

    private var pendingPayload: Data?
    private var onComplete: ((Bool) -> Void)?

    override init() {
        super.init()
        centralManager = CBCentralManager(delegate: self, queue: nil)
    }

    /// Stage a payload and kick off a fresh connection cycle.
    private func sendPayload(_ data: Data, completion: ((Bool) -> Void)?) {
        guard centralManager.state == .poweredOn else {
            completion?(false)
            return
        }

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
        while offset < data.count {
            let chunk = data.subdata(in: offset ..< min(offset + mtu, data.count))
            peripheral.writeValue(chunk, for: chr, type: .withoutResponse)
            offset += mtu
            usleep(5_000)             // tiny pause avoids radio congestion
        }
        print("✅ Sent \(data.count) bytes in \(Int(ceil(Double(data.count) / Double(mtu)))) packets")

        // Mark payload as consumed so that, should the connection fail and
        // reconnect, we don't send the same data again.
        pendingPayload = nil

        // Give the BLE stack enough time to flush the transmit queue before we
        // sever the link.  A full 64 × 64 PNG (~4 kB ≙ ≈ 200 packets) needs
        // roughly one second to reach the radio at 20 bytes / packet, so we
        // wait a full second before cancelling the connection.
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in
            guard let self else { return }
            self.centralManager.cancelPeripheralConnection(peripheral)
        }
    }
}


// MARK: – CBCentralManagerDelegate + CBPeripheralDelegate ---------------

extension BLEManager: CBCentralManagerDelegate, CBPeripheralDelegate {

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        guard central.state == .poweredOn else {
            print("⚠️  Bluetooth unavailable: \(central.state.rawValue)")
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
        print("🔍 Discovered \(peripheral.name ?? "unknown") (RSSI \(RSSI))")
        targetPeripheral = peripheral
        peripheral.delegate = self
        central.stopScan()
        central.connect(peripheral, options: nil)
    }

    func centralManager(_ central: CBCentralManager,
                        didConnect peripheral: CBPeripheral)
    {
        print("🔗 Connected to \(peripheral.name ?? "device")")
        peripheral.discoverServices([serviceUUID])
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
        guard
            let chr = service.characteristics?.first(where: { $0.uuid == characteristicUUID }),
            let payload = pendingPayload
        else { return }

        writeCharacteristic = chr
        transmit(payload, via: peripheral, characteristic: chr)
    }

    func centralManager(_ central: CBCentralManager,
                        didDisconnectPeripheral peripheral: CBPeripheral,
                        error: Error?)
    {
        let clean = (error == nil)
        if clean {
            print("🔌 Disconnected from \(peripheral.name ?? "device")")
        } else {
            print("⚠️  Disconnect error: \(error!.localizedDescription)")
        }

        targetPeripheral      = nil
        writeCharacteristic   = nil
        pendingPayload        = nil

        onComplete?(clean)
        onComplete = nil
    }
}
