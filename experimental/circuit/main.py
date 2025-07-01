from skidl import POWER, Part, TEMPLATE, Net, ERC, generate_netlist

# ------------------- Parameters ------------------------------------------------
NUM_PORTS      = 10
BUF_PER_PORT   = 2
RES_PER_PORT   = 1
FPGA_FOOTPRINT = 'Package_BGA:BGA-381_17x17_P0.80mm'
CONNECTOR_FOOT = 'Connector_IDC:IDC-02x08_Male_Vertical'
BUFFER_FOOT    = 'Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm'
RESARRAY_FOOT  = 'Resistor_THT:R_Array_SIP9'
CAP0402_FOOT   = 'Capacitor_SMD:C_0402'
VCC5   = Net('5V')
VCC3V3 = Net('3V3')
GND    = Net('GND')

# PART LIST
# FPGA = Part('Lattice_ECP5', 'LFE5U-45F-BG381', footprint=FPGA_FOOTPRINT)
# https://kicad.github.io/symbols/Connector_Generic
HUB75_HEADER = Part(
        'Connector_Generic',
        'Conn_02x08_Odd_Even',
        footprint=CONNECTOR_FOOT,
        dest=TEMPLATE
    )


# https://www.digikey.com/en/products/detail/jameco-electronics/74HCT245/26739286
BUFFER = Part('74xx', '74HCT245', footprint=BUFFER_FOOT)
RESARRAY = Part('Device', 'R_Network09', footprint=RESARRAY_FOOT)
CAP0402 = Part('Device', 'C', value='0.1u', footprint=CAP0402_FOOT)

# ------------------- Pin Map ----------------------------------------------------
HUB_75_NAMES = ['R1','G1','B1','R2','G2','B2','CLK','LAT','OE','A','B','C','D']

# ------------------------------------------------------------------------------ 
# Power pins always need nets before parts are instantiated.
VCC5.drive = POWER
VCC3V3.drive = POWER
GND.drive  = POWER

# ------------------- FPGA ------------------------------------------------------
fpga = Part('Lattice_ECP5', 'LFE5U-45F-BG381', footprint=FPGA_FOOTPRINT)

# Banks for 3v3 IO.
# Pins are illustrative; adapt to the bank/pin map from the data-sheet!
# TODO: FPGA Pin Map
fpga_io_pins = (
    'C3', 'B3', 'C4', 'B4', 'E2', 'D2', 'E1', 'D1',  # Bank-0 sample
    # ... add full list or read from CSV
)
io_iter = iter(fpga_io_pins)

# ------------------- HUB75 template nets ---------------------------------------
def hub75_nets(index):
    """Create the 13 active nets for one HUB75 port."""
    prefix = f'H{index}_'
    return {n: Net(prefix+n) for n in HUB_75_NAMES}

def generate_port(p: int):
    # TODO HUB75 specification + this connector
    hub = HUB75_HEADER
    hub.ref = f'J{p+1}'

    # TODO: Why this buffer
    bufs = [BUFFER for _ in range(BUF_PER_PORT)]
    for b,buf in enumerate(bufs):
        buf.ref = f'UB{p*BUF_PER_PORT + b + 1}'

    # TODO: Why this resistor
    rn = RESARRAY
    rn.ref = f'RN{p+1}'
    rn.value = '33'

    # -- Nets per HUB75 port --
    sig = hub75_nets(p)

    # 1) Wire FPGA → buffer inputs
    buf_bits = list(sig.values())
    # TODO: Why this pad - why 16 when 13?
    while len(buf_bits) < 16:
        buf_bits.append(Net(f'H{p}_NC{len(buf_bits)}'))

    for idx,buf in enumerate(bufs):
        in_pins  = buf.pins[2:10]
        out_pins = buf.pins[18:26]
        nets_seg = buf_bits[idx*8:(idx+1)*8]
        for i, (n, pin_in, pin_out) in enumerate(zip(nets_seg, in_pins, out_pins)):
            # Connect FPGA pin (next in list) → buffer.in
            current_fgpa_pin_index = idx*8 + i
            if current_fgpa_pin_index >= len(fpga_io_pins):
                raise ValueError(f'Exhausted FPGA I/Os!')
            fgpa_pin = fpga_io_pins[current_fgpa_pin_index]
            fpga[fpga_pin] += n
            pin_in += n
            pin_out += n
            
    # Tie buffer DIR low (A→B) and OE low (enable)
    for buf in bufs:
        buf['DIR'] += GND
        buf['OE']  += GND
        # Power
        buf['VCC'] += VCC5
        buf['GND'] += GND

    # 2) Series resistors on eight highest-speed lines (first 9 nets)
    for i, n in enumerate(list(sig.values())[:9]):
        rn[f'R{i+1,2}'] += n, hub[f'{(i//2)+1}.{(i%2)+1}']  # each SIP leg

    # 3) Remaining signals direct from buffer to HUB75 connector pins
    # Map connector pin names manually (1: R1, 2: G1 ... per HUB75 pinout)
    # TODO: What is E?
    pin_map = {
       1:'R1', 2:'G1', 3:'B1', 4:'E?', 5:'R2', 6:'G2', 7:'B2', 8:'GND',
       9:'CLK',10:'LAT',11:'OE',12:'A',13:'B',14:'C',15:'D',16:'GND'
    }
    for pin_num, name in pin_map.items():
        if name in sig:
            hub[str(pin_num)] += sig[name]
        else:
            hub[str(pin_num)] += GND

    # 4) Power pins –
    hub['8,16'] += GND   # explicit ground pins

def assembly():
    for p in range(NUM_PORTS):
        generate_port(p)

    # ------------------- Decoupling (example) --------------------------------------
    # 0.1uF caps on 3v3 near FPGA I/O banks
    for n in range(20):
        c = Part('Device', 'C', value='0.1u', footprint=CAP0402_FOOT)
        c.ref = f'CDEC{n+1}'
        c['1'] += VCC3V3
        c['2'] += GND

    # FPGA VCC and JTAG pins – simplified here
    fpga['VCCIO0,1,2,3,4,5,6,7'] += VCC3V3  # all I/O banks @3v3
    fpga['VCCA, VCCD_PLL0, VCCD_PLL1, VCORE'] += VCC3V3  # placeholder rails
    fpga['GND'] += GND

# ------------------- Generate Netlist -----------------------------------------
ERC()
assemby()
generate_netlist()
print('Netlist written as hub75_fpga_driver.net')
