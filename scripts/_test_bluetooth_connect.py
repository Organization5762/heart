from heart.peripheral.bluetooth import UartListener


listener = UartListener()
listener.start()
while True:
    for event in listener.consume_events():
        print(event)