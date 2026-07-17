"""loopsym — Simulink 원리를 배우는 교육용 미니 블록 다이어그램 시뮬레이터."""

from .core import Block, Diagram, Port, AlgebraicLoopError
from .blocks import (
    Constant, Step, Sine,
    Gain, Sum, Product, Saturation, PyFunction,
    Integrator, TransferFunction,
    UnitDelay, DiscreteIntegrator, DiscreteTransferFunction,
    Mux, Demux,
    Inport, Outport, Subsystem,
    Scope,
)
from .sim import Simulator, run, flatten
from .viz import export_json, render_html, save_json, load_json
from .webapi import run_simulation
from .realtime import run_realtime
from .ros2 import Ros2Publish, Ros2Subscribe   # rclpy 는 블록 생성 때만 필요 (지연 임포트)
from .drone import (                           # 드론 팔레트 (CLD-P65)
    QuadPlant, PID, RateController, AttitudeController, PositionController,
    QuadXMixer,
)
from .sensors import SensorBlock, IMU          # 센서 팔레트 (CLD-P62)
from .estimation import ComplementaryFilter    # 상태추정 팔레트 (CLD-P64)
