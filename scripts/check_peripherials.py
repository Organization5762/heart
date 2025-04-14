from heart.peripherial.manager import PeripherialManager
m = PeripherialManager()
d = m.detect()

peripherials = m.peripherials
print(len(peripherials))
print(peripherials)