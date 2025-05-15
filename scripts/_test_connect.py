from heart.peripheral.bluetooth import UartListener


listener = UartListener()
print("Starting")
listener.start()
print("Started")
while True:
    for event in listener.consume_events():
        print(event)