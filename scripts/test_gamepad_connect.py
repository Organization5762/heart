def find_8bitdo_devices():
    import subprocess
    import time

    print("Scanning for 8BitDo controllers...")

    # Start scan in background
    scan_proc = subprocess.Popen(
        ["bluetoothctl", "scan", "on"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    # Give it time to discover devices
    time.sleep(10)
    # Get the list of devices
    result = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True)

    # Kill the scan process
    scan_proc.terminate()

    # Get all devices but highlight 8BitDo ones
    all_devices = []
    bitdo_devices = []

    for line in result.stdout.strip().split("\n"):
        all_devices.append(line)
        if "8BitDo" in line:
            bitdo_devices.append(line)

    # Display all results
    print("\nAll Bluetooth devices found:")
    for device in all_devices:
        if "8BitDo" in device or "Pro Controller" in device:
            print(f">>> {device} <<<")  # Highlight 8BitDo devices
        else:
            print(device)

    # Also return the 8BitDo devices specifically
    if bitdo_devices:
        print("\nFound 8BitDo controllers:", len(bitdo_devices))
        return bitdo_devices
    else:
        print(
            "No 8BitDo controllers found. Make sure your controller is in pairing mode."
        )
        return []


def check_device_status(mac_address):
    import subprocess
    
    # Check if the device is already connected
    result = subprocess.run(
        ["bluetoothctl", "info", mac_address], 
        capture_output=True, 
        text=True
    )
    
    is_paired = "Paired: yes" in result.stdout
    is_connected = "Connected: yes" in result.stdout
    
    return is_paired, is_connected


def pair_8bitdo(mac_address):
    import subprocess
    
    # Check current status
    is_paired, is_connected = check_device_status(mac_address)
    
    if is_connected:
        print(f"Device {mac_address} is already connected. No action needed.")
        return
    
    print(f"Attempting to connect to 8BitDo controller ({mac_address})...")
    
    if not is_paired:
        print("Device not paired. Pairing first...")
        subprocess.run(["bluetoothctl", "pair", mac_address])
        subprocess.run(["bluetoothctl", "trust", mac_address])
    
    # Try to connect
    connect_result = subprocess.run(
        ["bluetoothctl", "connect", mac_address],
        capture_output=True,
        text=True
    )
    
    if "Connection successful" in connect_result.stdout:
        print("Successfully connected to the controller!")
    else:
        print("Connection attempt completed. Check controller status.")


if __name__ == "__main__":
    devices = find_8bitdo_devices()
    if devices:
        # Extract MAC address from the first found device
        # Format is typically "Device XX:XX:XX:XX:XX:XX 8BitDo Controller"
        device_info = devices[0]
        parts = device_info.split()
        if len(parts) >= 2:
            mac_address = parts[1]
            pair_8bitdo(mac_address)
        else:
            print("Could not parse device information correctly")
