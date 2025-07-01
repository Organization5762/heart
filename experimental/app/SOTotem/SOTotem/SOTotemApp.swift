//
//  SOTotemApp.swift
//  SOTotem
//
//  Created by Sebastien Kerbrat on 5/18/25.
//

import SwiftUI

@main
struct SOTotemApp: App {
    @StateObject private var ble = BLEManager()

    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(ble)
        }
    }
}
