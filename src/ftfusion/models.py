"""Physical-unit data contracts shared by software and future FPGA models."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SensorSample:
    """One synchronized MVP sensor frame.

    Every value is expressed in SI-derived engineering units. ADC conversion,
    encoder decoding, and timestamp synchronization happen before this boundary.
    """

    timestamp_s: float
    strain_torque_nm: float
    phase_current_a: float
    encoder_position_rad: float
    temperature_c: float


@dataclass(frozen=True, slots=True)
class FusionOutput:
    """One fused output frame suitable for the future SPI register interface."""

    timestamp_s: float
    torque_nm: float
    strain_corrected_nm: float
    current_torque_nm: float
    encoder_position_rad: float
    valid: bool
