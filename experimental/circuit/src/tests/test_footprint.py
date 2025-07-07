from circuit.painter.bga import BGA
from circuit.painter.board import Footprint


def test_layer_names():
    footprint = Footprint.load(
        library_name="FPGA", name="BGA381C80P20X20_1700X1700X176N"
    )
    for i in range(0, 2):
        BGA(footprint).preview(wave=i)


if __name__ == "__main__":
    test_layer_names()