"""Infrared sensor array peripheral and positioning solver."""

from .constants import DEFAULT_DMA_BUFFER_SIZE as DEFAULT_DMA_BUFFER_SIZE
from .constants import \
    DEFAULT_RADIAL_LAYOUT_RADIUS as DEFAULT_RADIAL_LAYOUT_RADIUS
from .constants import SPEED_OF_LIGHT as SPEED_OF_LIGHT
from .dma import IRArrayDMAQueue as IRArrayDMAQueue
from .dma import IRDMAPacket as IRDMAPacket
from .dma import IRSample as IRSample
from .dma import compute_crc as compute_crc
from .frames import FrameAssembler as FrameAssembler
from .frames import IRFrame as IRFrame
from .layout import radial_layout as radial_layout
from .peripheral import \
    DEFAULT_CONVERGENCE_THRESHOLD as DEFAULT_CONVERGENCE_THRESHOLD
from .peripheral import DEFAULT_MAX_ITERATIONS as DEFAULT_MAX_ITERATIONS
from .peripheral import DEFAULT_SOLVER_METHOD as DEFAULT_SOLVER_METHOD
from .peripheral import DEFAULT_USE_JACOBIAN as DEFAULT_USE_JACOBIAN
from .peripheral import IRSensorArray as IRSensorArray
from .solver import MultilaterationSolver as MultilaterationSolver
