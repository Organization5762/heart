from circuit.painter.board import Footprint, Measurement
import pcbnew
from collections import defaultdict
import matplotlib.pyplot as plt
from circuit.painter.board import Layer
import logging
import math
logger = logging.getLogger(__name__)

# TODO: Hardocoded, should be derived from the pads
OFFSET_VALUE = 0.4
BASE_LENGTH = 3

class Wave:
    def __init__(self, perimeter_points):
        self.occupied = {(x, y) for (x, y) in perimeter_points}

    # Useful helpers
    def clear_left(self, location) -> bool:
        # no pad with same y and strictly smaller x
        return all(y != location.y or x >= location.x
                for (x, y) in self.occupied)

    def clear_right(self, location) -> bool:
        return all(y != location.y or x <= location.x
                for (x, y) in self.occupied)

    def clear_up(self, location) -> bool:     # +y  (swap sign if your axis is flipped)
        return all(x != location.x or y <= location.y
                for (x, y) in self.occupied)

    def clear_down(self, location) -> bool:   # -y
        return all(x != location.x or y >= location.y
                for (x, y) in self.occupied)


class BGA:
    def __init__(self, footprint):
        """`footprint` is a pcbnew.FOOTPRINT object (e.g. board.FindFootprintByReference("U1"))"""
        self.fp   = footprint.kicad()
        self.pads = list(self.fp.Pads())

        # Pad to name
        self.pad_to_name = {
            pad.GetPadName() or pad.GetNumber(): pad
            for pad in self.pads
        }

        # ---- Build a discrete grid ----------------------------------------------------------
        xy = [(p.GetPosition().x, p.GetPosition().y) for p in self.pads]
        pitch = min(
            d for i,a in enumerate(xy) for b in xy[i+1:]
            for d in (abs(a[0]-b[0]), abs(a[1]-b[1])) if d
        )
        ox, oy = min(x for x,_ in xy), min(y for _,y in xy)
        self.grid = {}
        for pad,(x,y) in zip(self.pads, xy):
            i = round((x-ox)/pitch)
            j = round((y-oy)/pitch)
            self.grid[(i,j)] = pad

        xs, ys = zip(*self.grid.keys())
        self.cx = (min(xs)+max(xs)) / 2
        self.cy = (min(ys)+max(ys)) / 2

    def _compute_perimeter(self, wave:int=0):
        """Shortcut: perimeter of a specific wave (0 == outermost)."""
        remaining = set(self.grid.keys())
        waves = []
        while remaining:
            ring = [pt for pt in remaining if self._is_perimeter_pad(pt, remaining)]
            if not ring:
                break
            waves.append([self.grid[pt].GetPadName() or self.grid[pt].GetNumber()
                           for pt in ring])
            remaining -= set(ring)
        return waves[wave] if wave < len(waves) else []

    # ---------------------------------------------------------------------
    # ------------------------------ helpers ------------------------------
    def _quadrant(self, i, j):
        if i >= self.cx and j >= self.cy: return 1
        if i <  self.cx and j >= self.cy: return 2
        if i <  self.cx and j <  self.cy: return 3
        return 4

    def _is_perimeter_pad(self, pt, population):
        i, j   = pt
        nbr    = lambda dx,dy: (i+dx, j+dy) in population
        R = nbr(+1,0);  L = nbr(-1,0);  U = nbr(0,+1);  D = nbr(0,-1)

        # TODO: This doesn't support diagonal openings even though, if they're facing outward,
        # might afford the ability to route a given pad out of the BGA.
        if R and L and U and D:
            return False

        q  = self._quadrant(i, j)
        missing = {
            1: (not R) or (not U),
            2: (not L) or (not U),
            3: (not L) or (not D),
            4: (not R) or (not D),
        }[q]
        return missing == 1

    def draw_tracks(self, board_layer: Layer, wave: int = 0) -> None:
        perimeter = self._compute_perimeter(wave)
        if len(perimeter) == 0:
            return

        perimeter_points = [(self.pad_to_name[pad_name].GetPosition().x, self.pad_to_name[pad_name].GetPosition().y) for pad_name in perimeter]

        wave_obj = Wave(perimeter_points)
        for i, pad_name in enumerate(perimeter):
            location = self.pad_to_name[pad_name].GetPosition()
            if location is None:
                continue

            dx, dy = None, None
            if wave % 2 == 0:
                if wave_obj.clear_left(location):
                    dx, dy = (-BASE_LENGTH, 0)
                if wave_obj.clear_right(location):
                    dx, dy = (BASE_LENGTH, 0)
                if wave_obj.clear_up(location):
                    dx, dy = (0, BASE_LENGTH)
                if wave_obj.clear_down(location):
                    dx, dy = (0, -BASE_LENGTH)

                if dx is None and dy is None:
                    continue

                board_layer.track(
                    Measurement.from_nm(location.x),
                    Measurement.from_nm(location.y),
                    Measurement.from_nm(location.x) + Measurement.from_mm(dx),
                    Measurement.from_nm(location.y) + Measurement.from_mm(dy)
                )
            elif wave % 2 == 1:
                offset = OFFSET_VALUE
                if wave_obj.clear_left(location):
                    dx, dy = (-BASE_LENGTH, offset)
                if wave_obj.clear_right(location):
                    dx, dy = (BASE_LENGTH, offset)
                if wave_obj.clear_up(location):
                    dx, dy = (offset,  BASE_LENGTH)
                if wave_obj.clear_down(location):
                    dx, dy = (offset, -BASE_LENGTH)

                if dx is None and dy is None:
                    continue

                board_layer.bent_track(
                    Measurement.from_nm(location.x),
                    Measurement.from_nm(location.y),
                    Measurement.from_nm(location.x) + Measurement.from_mm(dx),
                    Measurement.from_nm(location.y) + Measurement.from_mm(dy)
                )

    def preview(self, wave: int = 0) -> None:
        # Create an axis if the caller didn't
        color = "tab:orange"
        _, ax = plt.subplots(figsize=(6, 6), constrained_layout=True)

        # --- 1. Draw every pad as a grey outline ---------------------------------
        xs_all, ys_all = zip(*self.grid.keys())
        ax.scatter(
            xs_all,
            ys_all,
            s=200,
            facecolors="none",
            edgecolors="0.7",
            linewidth=1,
            zorder=1
        )

        # --- 2. Highlight the requested ring -------------------------------------
        ring_pad_names = set(self._compute_perimeter(wave))
        ring_pts = [pt for pt, pad in self.grid.items()
                    if (pad.GetPadName() or pad.GetNumber()) in ring_pad_names]

        if not ring_pts:
            raise ValueError(f"No wave {wave} found")

        xs_ring, ys_ring = zip(*ring_pts)
        ax.scatter(xs_ring, ys_ring,
                s=220,
                c=color,
                edgecolors="black",
                linewidth=0.8,
                zorder=3)

        # Optional pad labels
        for (i, j) in ring_pts:
            pad = self.grid[(i, j)]
            label = pad.GetPadName() or pad.GetNumber()
            ax.text(i, j, label,
                    ha="center", va="center",
                    fontsize=6, color="black", zorder=4)

        # --- 3. Nice-looking axes -------------------------------------------------
        ax.set_aspect("equal", adjustable="box")
        ax.invert_yaxis()         # KiCad’s Y axis points down
        ax.axis("off")            # no ticks or frame
        plt.show()