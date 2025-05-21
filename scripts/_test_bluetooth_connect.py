from heart.peripheral.switch import BluetoothSwitch

for l in BluetoothSwitch.detect():
    print("Starting")
    l.listener.start()
    print("Started listener")
    while True:
        for event in l.listener.consume_events():
            print(event)