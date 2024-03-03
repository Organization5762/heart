from openant.device.heart_rate import HeartRateData

class HeartRateDataStore:
    def __init__(self) -> None:
        self.values = []

    # TODO: We can discard old data
    def list_values(self) -> list[HeartRateData]:
        return self.values

    def add(self, data: HeartRateData) -> None:
        self.values.append(data)
        if len(self.values) > 100:
            self.values = self.values[-100:]