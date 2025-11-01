from heart.peripheral.switch import BluetoothSwitch


for bluetooth_switch in BluetoothSwitch.detect():
    print("Starting")
    bluetooth_switch.listener.start()
    print("Started listener")
    while True:
        for event in bluetooth_switch.listener.consume_events():
            print(event)
