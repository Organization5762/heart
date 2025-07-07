from circuit.painter.board import Board, Footprint, Measurement
import pytest

from circuit.painter.bga import BGA


def test_layer_names():
    assert board.get_layer(1).get_layer_name() == "In1_Cu"
    assert board.get_layer(2).get_layer_name() == "In2_Cu"
    assert board.get_layer(3).get_layer_name() == "In3_Cu"
    assert board.get_layer(4).get_layer_name() == "In4_Cu"
    assert board.get_layer(5).get_layer_name() == "In5_Cu"
    assert board.get_layer(6).get_layer_name() == "In6_Cu"

    with pytest.raises(ValueError):
        board.get_layer(7)

def test_create_bga_tracks():
    board = Board(layers=6, width=Measurement.from_mm(300), height=Measurement.from_mm(200))
    footprint = Footprint.load(
        library_name="FPGA", name="BGA381C80P20X20_1700X1700X176N"
    )
    board.get_layer(1).footprint(
        x=Measurement.from_mm(100), y=Measurement.from_mm(100),
        footprint=footprint
    )
    bga = BGA(footprint)
    bga.draw_tracks(board.get_layer(1), wave=0)
    bga.draw_tracks(board.get_layer(1), wave=1)


    # Place the resistors, capacitors, buffer, etc.


    board.save(directory="/tmp", name="test")

if __name__ == "__main__":
    test_create_bga_tracks()