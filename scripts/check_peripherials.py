from heart.peripheral.manager import PeripheralManager
m = PeripheralManager()
d = m.detect()

peripheral = m.peripheral
print(len(peripheral))
print(peripheral)