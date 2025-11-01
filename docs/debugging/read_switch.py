import serial

ser = serial.Serial("/dev/ttyACM0", 115200)

try:
    while True:
        if ser.in_waiting > 0:
            # TODO (lampe): Handle button state too
            # Will likely switch this over to a JSON format + update the driver on the encoder
            data = ser.readline().decode("utf-8").rstrip()
            print(data)
except KeyboardInterrupt:
    print("Program terminated")
finally:
    ser.close()
