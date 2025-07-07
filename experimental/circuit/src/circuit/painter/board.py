from dataclasses import dataclass
import os
from datetime import datetime
import random
from re import S
from typing import Any, Optional
import pcbnew
import math

@dataclass
class Measurement:
    value: float
    unit: str

    def __str__(self) -> str:
        return f"{self.value} {self.unit}"

    @classmethod
    def from_mm(cls, value: float) -> 'Measurement':
        return cls(
            value=value,
            unit="mm"
        )

    @classmethod
    def from_nm(cls, value: float) -> 'Measurement':
        return cls(
            value=value,
            unit="nm"
        )

    @classmethod
    def from_mil(cls, value: float) -> 'Measurement':
        return cls(
            value=value,
            unit="mil"
        )

    def millimeters(self) -> float:
        if self.unit == "mm":
            return self.value
        elif self.unit == "mil":
            return self.value * 0.0254
        elif self.unit == "nm":
            return self.value * 1e-6
        else:
            raise ValueError(f"Invalid unit: {self.unit}")

    def __add__(self, other: 'Measurement') -> 'Measurement':
        return Measurement(
            value=self.millimeters() + other.millimeters(),
            unit="mm"
        )

    def __sub__(self, other: 'Measurement') -> 'Measurement':
        return Measurement(
            value=self.millimeters() - other.millimeters(),
            unit="mm"
        )

    def __mul__(self, other: 'Measurement') -> 'Measurement':
        return Measurement(
            value=self.millimeters() * other.millimeters(),
            unit="mm"
        )

    def __truediv__(self, other: 'Measurement') -> 'Measurement':
        return Measurement(
            value=self.millimeters() / other.millimeters(),
            unit="mm"
        )



class Manager:
    @classmethod
    def get_footprint(
        cls,
        library_name: str,
        name: str
    ) -> Any:
        LIBRARY_PATH = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/"
        return pcbnew.FootprintLoad(
            libname=os.path.join(
                LIBRARY_PATH,
                f"{library_name}.pretty",
            ),
            name=name
        )

class Footprint:
    def __init__(self, footprint: Any) -> None:
        self.footprint = footprint

    @classmethod
    def load(cls, library_name: str, name: str) -> 'Footprint':
        return cls(
            footprint=Manager.get_footprint(library_name=library_name, name=name)
        )
    
    def kicad(self) -> Any:
        return self.footprint

@dataclass
class Layer:
    board: 'Board'
    layer_number: int
    # Min manufacturable trace is 4mil(0.1mm)
    # - Strongly suggest to design trace above 6mil(0.15mm) to save cost (PCBWAY)
    # - Lattice recommends 4mil in their example packaging, though
    draw_width: Measurement = Measurement.from_mil(value=4)

    def get_layer_name(self) -> str:
        if self.layer_number == 0:
            return "F_Cu"
        elif self.layer_number == len(self.board.layers):
            return "B_Cu"

        # https://gitlab.com/kicad/code/kicad/-/blob/master/include/layer_ids.h
        return f"In{self.layer_number + 2}_Cu"

    def track(self, x1: Measurement, y1: Measurement, x2: Measurement, y2: Measurement) -> None:
        self._verify_within_bounds(x1, y1)
        self._verify_within_bounds(x2, y2)

        # TODO: Configure draw width
        track = pcbnew.PCB_TRACK(self.board.kicad())
        track.SetWidth(pcbnew.FromMM(self.draw_width.millimeters()))
        track.SetLayer(self._get_pcbnew_layer())
        track.SetStart(pcbnew.VECTOR2I_MM(x1.millimeters(), y1.millimeters()))
        track.SetEnd(pcbnew.VECTOR2I_MM(x2.millimeters(), y2.millimeters()))
        self.board._add(track)

    def bent_track(
        self,
        x1: Measurement, y1: Measurement,
        x2: Measurement, y2: Measurement
    ) -> None:
        """
        Route a two-segment track:
            ┌──────── 1st segment: exactly 45 ° from the start point
            └──────── 2nd segment: purely horizontal or vertical, whichever axis
                                had the *larger* absolute delta

        The 45 ° leg always travels the *smaller* of |Δx| and |Δy| so the bend
        ends on the axis that already almost lines up with the destination.
        """
        # ---- Sanity & helpers -------------------------------------------------
        self._verify_within_bounds(x1, y1)
        self._verify_within_bounds(x2, y2)

        dx = x2.millimeters() - x1.millimeters()
        dy = y2.millimeters() - y1.millimeters()

        if dx == 0 or dy == 0:
            self.track(x1, y1, x2, y2)
            return

        if abs(dx) < abs(dy):
            step = abs(dx)
            xb = x2.millimeters()                                           
            yb = y1.millimeters() + math.copysign(step, dy)               
        else:
            step = abs(dy)
            xb = x1.millimeters() + math.copysign(step, dx)                
            yb = y2.millimeters()

        xb = Measurement(
            value=xb,
            unit="mm"
        )          
        yb = Measurement(
            value=yb,
            unit="mm"
        )                              

        # 1) 45 ° leg
        seg1 = pcbnew.PCB_TRACK(self.board.kicad())
        seg1.SetWidth(pcbnew.FromMM(self.draw_width.millimeters()))
        seg1.SetLayer(self._get_pcbnew_layer())
        seg1.SetStart(
            pcbnew.VECTOR2I(pcbnew.FromMM(x1.millimeters()), pcbnew.FromMM(y1.millimeters()))
        )
        seg1.SetEnd(
            pcbnew.VECTOR2I(pcbnew.FromMM(xb.millimeters()), pcbnew.FromMM(yb.millimeters()))
        )
        self.board._add(seg1)

        seg2 = pcbnew.PCB_TRACK(self.board.kicad())
        seg2.SetWidth(pcbnew.FromMM(self.draw_width.millimeters()))
        seg2.SetLayer(self._get_pcbnew_layer())
        seg2.SetStart(
            pcbnew.VECTOR2I(pcbnew.FromMM(xb.millimeters()), pcbnew.FromMM(yb.millimeters()))
        )
        seg2.SetEnd(
            pcbnew.VECTOR2I(pcbnew.FromMM(x2.millimeters()), pcbnew.FromMM(y2.millimeters()))
        )
        self.board._add(seg2)

    def mm_point(self, x_mm, y_mm):
        """KiCad 8: convert mm → internal units in one call."""
        return pcbnew.wxPoint(int(round(pcbnew.IU_PER_MM * x_mm)),
                              int(round(pcbnew.IU_PER_MM * y_mm)))

    def footprint(self, x: Measurement, y: Measurement, footprint: Footprint, reference: Optional[str] = None) -> None:
        self._verify_within_bounds(x, y)

        if reference is None:
            # TODO:
            designator = random.randint(1, 1000000)
            reference = f'P{designator}'

        f = footprint.footprint
        f.SetPosition(
            pcbnew.VECTOR2I_MM(x.millimeters(), y.millimeters())
        )
        f.SetOrientation(pcbnew.EDA_ANGLE(0, pcbnew.DEGREES_T))
        f.SetReference(reference)
        f.Reference().SetVisible(True)

        self.board._add(footprint.footprint)

    def _verify_within_bounds(self, x: Measurement, y: Measurement) -> None:
        

        assert x.millimeters() < 500 and y.millimeters() < 500 and x.millimeters() > -1 and y.millimeters() > -1, f"Coordinates {x}, {y} are out of bounds"


    def _get_pcbnew_layer(self) -> Any:
        return getattr(pcbnew, self.get_layer_name())

class Board:
    def __init__(self, width: Measurement, height: Measurement, layers: int) -> None:
        self._layers = [
            Layer(
                board=self,
                layer_number=i
            ) for i in range(layers)
        ]

        self.ORIGIN = pcbnew.VECTOR2I_MM(0, 0)
        self.board = pcbnew.CreateEmptyBoard()

        ###
        # Initialize board size
        ###
        self.board.SetLayerName(
            pcbnew.Edge_Cuts,
            "Edge.Cuts"
        )


        poly = pcbnew.PCB_SHAPE(self.board, pcbnew.SHAPE_T_POLY)
        poly.SetWidth(pcbnew.FromMM(0.1))
        poly.SetLayer(pcbnew.Edge_Cuts)
        poly.SetPolyPoints([
            pcbnew.VECTOR2I_MM(0, 0),
            pcbnew.VECTOR2I_MM(width.millimeters(), 0),
            pcbnew.VECTOR2I_MM(width.millimeters(), height.millimeters()),
            pcbnew.VECTOR2I_MM(0, height.millimeters()),
        ])
            
        self.board.Add(poly)

        self.group = pcbnew.PCB_GROUP(self.board)
        self.board.Add(self.group)


        # Initalize the board:
        # 1. Set the number of layers
        # 2. Set which layers are available
        design = self.board.GetDesignSettings()
        design.SetCopperLayerCount(layers)
        lset = self.board.GetVisibleLayers()
        for name in range(1, (layers - 3), 1):
            layer_obj = getattr(pcbnew, f"In{name}_Cu")
            self.board.SetLayerName(
                layer_obj,
                f"In{name}.Cu"
            )
            lset.AddLayer(layer_obj)

        self.board.SetVisibleLayers(lset)

    def _add(self, item: Any) -> None:
        self.board.Add(item)
        self.group.AddItem(item)

    def kicad(self) -> Any:
        return self.board

    def get_layers(self) -> list[Layer]:
        return self._layers

    def get_layer(self, n:int) -> Layer:
        if n > len(self._layers):
            raise ValueError(f"Layer {n} does not exist - only {len(self._layers)} layers")

        return self._layers[n-1]

    def _finalize_board(self) -> None:
        # https://github.com/Blinkinlabs/circuitpainter/blob/8bb1d4ce52137c84f8e698f1c34e3ee9bef9ca39/src/circuitpainter/circuitpainter.py#L591
        self.kicad().BuildConnectivity()
        filler = pcbnew.ZONE_FILLER(self.kicad())
        zones = self.kicad().Zones()
        filler.Fill(zones)

        boundary = self.kicad().GetBoardEdgesBoundingBox()
        x = boundary.GetX()
        y = boundary.GetY() + boundary.GetHeight()

        settings = self.kicad().GetDesignSettings()
        settings.SetAuxOrigin(pcbnew.VECTOR2I(x,y))

    def _name_board(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        block = pcbnew.TITLE_BLOCK()
        block.SetTitle("Test")
        block.SetDate(today)
        block.SetRevision("1.0")
        block.SetCompany("Organization 5762")
        self.kicad().SetTitleBlock(
            block
        )

    def save(self, directory: str, name: str) -> None:
        self._finalize_board()
        self._name_board()

        self.kicad().Save(os.path.join(directory, f"{name}.kicad_pcb"))