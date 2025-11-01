from dataclasses import dataclass
import string
from skidl import *
from skidl.pin import pin_types
import logging
from collections import Counter

logger = logging.getLogger(__name__)

# ------------------- Nets & Power Rails ---------------------------------
VCC5      = Net('5V');   VCC5.drive   = POWER
VCC3V3    = Net('3V3');  VCC3V3.drive = POWER
VCORE_1V2 = Net('VCORE_1V2'); VCORE_1V2.drive = POWER
GND       = Net('GND');  GND.drive    = POWER

# ------------------- Configuration --------------------------------------
class BoardConfig:
    """Central location for board‑level constants."""

    # High‑level params
    NUM_PORTS     = 10
    BUF_PER_PORT  = 2  # 8‑bit buffers per HUB75 port
    BUF_SIZE = 8
    RES_PER_PORT  = 1  # SIP‑9 resistor array per port
    RESARRAY_NAME = "R_Pack09_Split"

    # Libraries & device names
    SNAP_EDA  = 'SnapEDA-Library'
    FGPA_NAME = 'LFE5U-45F-7BG256I'

    # Footprints
    FPGA_FOOTPRINT  = 'BGA381C80P20X20_1700X1700X176N'
    CONNECTOR_FOOT  = 'Connector_IDC:IDC-Header_2x08_P2.54mm_Vertical'
    RESARRAY_FOOT   = 'Resistor_THT:R_Array_SIP9'
    CAP0402_FOOT    = 'Capacitor_SMD:C_0402_1005Metric'
    CAP0805_FOOT    = 'Capacitor_SMD:C_0805_2012Metric'

    # HUB75 signal ordering
    HUB_75_NAMES = ['R1','G1','B1', 'E', 'R2','G2','B2','CLK','LAT','OE','A','B','C','D']
    HUB75_WIRE_ORDER = ['CLK', 'LAT', 'OE',
                    'R1','G1','B1','R2','G2','B2',
                    'A','B','C','D','E']

    HUB_75_WIRE_ROWS = {
        0: ["CLK", "LAT", "OE"],
        2: ['R1','G1','B1'],
        3: ["B2", 'R2', 'G2', 'A'],
        4: ["B", "C", "D", "E"],
    }

    def buffer_part(self) -> Part:
        # https://www.nexperia.com/product/74HCT245BQ
        return Part("74HCT245BQ_115", "74HCT245BQ,115", footprint="Package_SO:74HCT245BQ115")
# ------------------- Board Builder --------------------------------------
class Hub75DriverBoard:
    """Builds an ECP5‑based multi‑port HUB75 splitter board."""

    def __init__(self, cfg: BoardConfig | None = None):
        self.cfg = cfg or BoardConfig()
        self._create_fpga()
        self.allocator = FPGAPinAllocator(
            fpga=self.fpga
        )

    # ------------------------------------------------------------------
    #   FPGA setup helpers
    # ------------------------------------------------------------------
    def _create_fpga(self):
        self.fpga = Part(self.cfg.SNAP_EDA, self.cfg.FGPA_NAME, footprint=self.cfg.FPGA_FOOTPRINT)
        self.fpga_io_pins = self._gather_io_pins()

    def _gather_io_pins(self):
        logger.info("FPGA pin function histogram: %s", Counter([p.func for p in self.fpga.pins]))
        pins = [p.num for p in self.fpga.pins if p.func == pin_types.BIDIR]
        if not pins:
            raise RuntimeError("No bidirectional IO pins found on FPGA symbol.")
        return pins

    # ------------------------------------------------------------------
    #   Generic utilities
    # ------------------------------------------------------------------
    def _hub75_nets(self, idx):
        """Return dict of 13 signal nets for port *idx*."""
        prefix = f'H{idx}_'
        return {name: Net(prefix + name) for name in self.cfg.HUB_75_NAMES}

    def _add_decoupling(self, pin_regex, cap_val='0.1u', count_per_pin=1):
        for p in self.fpga.get_pins(pin_regex):
            for _ in range(count_per_pin):
                c = Part('Device', 'C', value=cap_val, footprint=self.cfg.CAP0402_FOOT)
                c[1] += p.net
                c[2] += GND

    # ------------------------------------------------------------------
    #   Per‑port helpers (namespacing fixed)
    # ------------------------------------------------------------------
    def _create_port_buffers(self, idx):
        """Instantiate fresh buffer parts so refs don't collide between ports."""
        bufs = []
        for b in range(self.cfg.BUF_PER_PORT):
            buf = self.cfg.buffer_part()
            buf.ref = f'UB{idx}_{chr(ord("A")+b)}'
            bufs.append(buf)
        return bufs

    def _create_res_array(self, idx):
        rn = Part('Device', self.cfg.RESARRAY_NAME, value='33', footprint=self.cfg.RESARRAY_FOOT)
        rn.ref = f'RN{idx}'
        return rn

    # ---- HUB75 connector ----------------------------------------------
    def _create_hub75_connector(self, idx):
        hub = Part('Connector_Generic', 'Conn_02x08_Odd_Even', footprint=self.cfg.CONNECTOR_FOOT)
        hub.ref = f'J{idx}'
        return hub

    def _map_hub75_pins(self, hub, sig):
        """Wire logical HUB75 signals to physical header pins."""
        pin_map = {
            1:'R1', 2:'G1', 3:'B1', 4:'E', 5:'R2', 6:'G2', 7:'B2', 8:'GND',
            9:'CLK',10:'LAT',11:'OE',12:'A',13:'B',14:'C',15:'D', 16:'GND'
        }
        for pin_num, name in pin_map.items():
            hub[str(pin_num)] += sig.get(name, GND)
        hub['8,16'] += GND  # dedicated grounds

    # ---- Buffer handling ----------------------------------------------
    def _wire_fpga_to_buffers(self, port_idx, bufs, sig):
        """
        Fan the 13 HUB75 nets (plus 3 NC pads) through two 74HCT244s.

        • FPGA-IO  →  244 “A” pins   (via a private *_IN net)
        • 244 “Y”  →  public net     (shared with resistor-pack + connector)
        """
        # --- Fill to 16 lines so the two octal buffers are fully used ----
        order = []
        for x in self.cfg.HUB_75_WIRE_ROWS.values():
            order.extend(x)
        buf_bits = [sig[n] for n in order]

        while len(buf_bits) < self.cfg.BUF_SIZE * self.cfg.BUF_PER_PORT:
            pad_idx = len(buf_bits)
            buf_bits.append(Net(f'BF{port_idx}_NC{pad_idx}'))

        # Grab an allocated region for this buffer
        # Max of all the values
        allocated_pins = self.allocator.allocate_region(
            col_size=max([len(x) for x in self.cfg.HUB_75_WIRE_ROWS.values()]),
            row_size=max(self.cfg.HUB_75_WIRE_ROWS.keys()) + 1
        )

        # Now we have to do two things:
        # 1. Allocate FPGA pins for each (This is easy, we have the index in HUB_75_WIRE_ROWS)
        # 2. Allocate a buffer pin for each
        io_cursor = 0

        for row, values in self.cfg.HUB_75_WIRE_ROWS.items():
            for i, value in enumerate(values):
                buf_idx = int(io_cursor / self.cfg.BUF_SIZE)
                current_buf_idx = io_cursor % self.cfg.BUF_SIZE
                buf = bufs[buf_idx]
                net = buf_bits[io_cursor]

                net_in = Net(f'{net.name}_IN')

                fpga_pin = allocated_pins[row][i]
                self.fpga[fpga_pin] += net_in

                buf[f"A{current_buf_idx}"]            += net_in
                buf[f"B{current_buf_idx}"]            += net

                io_cursor += 1


    def _configure_buffers(self, bufs):
        for buf in bufs:
            # 245 variant has DIR; 244 variant has dual OE lines.
            try:
                buf['DIR'] += GND
                buf[r'~{OE}'] += GND
                buf['GND_1'] += GND
                buf['GND_2'] += GND
            except:
                buf['1OE'] += GND
                buf['2OE'] += GND
                buf['GND'] += GND
            buf['VCC'] += VCC5

            cdec = Part('Device', 'C', value='0.1u', footprint=self.cfg.CAP0402_FOOT)
            cdec[1] += VCC5
            cdec[2] += GND

    # ---- Series resistors ---------------------------------------------
    def _add_series_resistors(self, rn, sig, hub) -> None:
        for r_idx, n in enumerate(list(sig.values())[:9], start=1):
            resistor_sym = f'R{r_idx}'
            rn[f'{resistor_sym}.1'] += n
            rn[f'{resistor_sym}.2'] += hub[str(r_idx)]

    # ------------------------------------------------------------------
    #   Port factory – orchestrates the helpers above
    # ------------------------------------------------------------------
    def _generate_port(self, idx):
        sig  = self._hub75_nets(idx)
        bufs = self._create_port_buffers(idx)
        rn   = self._create_res_array(idx)
        hub  = self._create_hub75_connector(idx)

        self._wire_fpga_to_buffers(idx, bufs, sig)
        self._configure_buffers(bufs)
        self._map_hub75_pins(hub, sig)
        self._add_series_resistors(rn, sig, hub)

    # ------------------------------------------------------------------
    #   Complete board assembly
    # ------------------------------------------------------------------
    def assemble(self):
        for idx in range(self.cfg.NUM_PORTS):
            self._generate_port(idx)

        # ---- Power tree ------------------------------------------------
        V3_RAILS  = r'VCCIO.*'
        V2_RAILS  = r'VCC(?!IO).*|VCORE|VCCD.*'
        AUX_RAILS = r'VCCAUX.*'

        self.fpga[Rgx(V3_RAILS)] += VCC5
        self._add_decoupling(Rgx(V3_RAILS), '0.1u')

        self.fpga[Rgx(V2_RAILS)] += VCORE_1V2
        self._add_decoupling(Rgx(V2_RAILS), '0.1u')
        for _ in range(3):
            bulk = Part('Device', 'C', value='4.7u', footprint=self.cfg.CAP0805_FOOT)
            bulk[1] += VCORE_1V2
            bulk[2] += GND

        self.fpga[Rgx(AUX_RAILS)] += VCC5
        self._add_decoupling(Rgx(AUX_RAILS), '1u')
        self._add_decoupling(Rgx(AUX_RAILS), '0.1u')
        self.fpga[Rgx('GND.*')] += GND

    # ------------------------------------------------------------------
    #   Public API
    # ------------------------------------------------------------------
    def build(self):
        self.assemble()
        ERC()
        generate_netlist(tool=KICAD8)
        print('Netlist written as hub75_fpga_driver.net')


class FPGAPinAllocator:
    ROWS = list(string.ascii_uppercase[:18])         # 'A' … 'R'
    COLS = list(range(1, 17))                        # 1 … 16

    def __init__(self, fpga: Part) -> None:
        self.fpga = fpga
        self._grid: dict[tuple[str, int], str] = {}  # (row, col) → pin-name
        self._used: set[str] = set()                # already-taken pin names
        self._populate_grid()
        self.counter = 0

    def allocate_region(
        self,
        *,
        col_size = 4,
        row_size = 5,
        start_at: tuple[str, int] | None = None
    ) -> list[list[str]]:
        all_valid = []
        
        # Get all the unique numbers
        rows = sorted(list(set([x[0] for x in self._grid])))
        columns = sorted(list(set([x[1] for x in self._grid])))
        for row_start in range(0, len(rows), row_size):
            row_names = rows[row_start:row_start + row_size]

            for col_start in range(0, len(columns), col_size):
                col_names = columns[col_start:col_start + col_size]
                
                if len(row_names) < row_size or len(col_names) < col_size:
                    continue
                all_valid.append((row_names, col_names))

        if self.counter < len(all_valid):
            combinations = []
            rows, cols = all_valid[self.counter] 
            for row in rows:
                result = []
                for col in cols:
                    result.append(f"{row}{col}")
                combinations.append(result)

            self.counter += 1
            return combinations

        raise RuntimeError(f"No {row_size}×{col_size} IO region left on the FPGA. Ran out on board {self.counter}")

    # ------------------------------------------------------------------
    #   Internals
    # ------------------------------------------------------------------
    def _populate_grid(self) -> None:
        """Map bidirectional pins into a 2-D dict keyed by (row, col)."""
        for p in self.fpga.pins:
            if p.func != pin_types.BIDIR:
                continue
            try:
                row, col = self._decode_pin_name(p.num)
            except ValueError:
                continue          # skip weirdly-named balls
            self._grid[(row, col)] = p.num

    @staticmethod
    def _decode_pin_name(name: str) -> tuple[str, int]:
        """
        Convert 'A3' → ('A', 3).  Works for one- or two-letter rows (e.g. 'AA14').
        """
        row = ''.join(ch for ch in name if ch.isalpha())
        col = ''.join(ch for ch in name if ch.isdigit())
        if not row or not col:
            raise ValueError(f"Unrecognised ball name: {name}")
        return row, int(col)

# ------------------- Script entrypoint -----------------------------------
if __name__ == '__main__':
    Hub75DriverBoard().build()
