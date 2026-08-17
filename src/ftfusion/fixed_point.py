"""Bit-accurate fixed-point model for the future HLS implementation."""

from dataclasses import dataclass
from math import ceil, floor, isfinite

from .complementary import FusionConfig
from .models import FusionOutput, SensorSample


@dataclass(frozen=True, slots=True)
class QFormat:
    """Signed, saturating two's-complement fixed-point format."""

    total_bits: int = 32
    fractional_bits: int = 16

    def __post_init__(self) -> None:
        if self.total_bits < 2:
            raise ValueError("total_bits must be at least 2")
        if not 0 <= self.fractional_bits < self.total_bits:
            raise ValueError("fractional_bits must fit inside total_bits")

    @property
    def scale(self) -> int:
        return 1 << self.fractional_bits

    @property
    def minimum_raw(self) -> int:
        return -(1 << (self.total_bits - 1))

    @property
    def maximum_raw(self) -> int:
        return (1 << (self.total_bits - 1)) - 1

    def saturate(self, raw: int) -> int:
        return min(self.maximum_raw, max(self.minimum_raw, raw))

    @staticmethod
    def _round_half_away_from_zero(value: float) -> int:
        return floor(value + 0.5) if value >= 0 else ceil(value - 0.5)

    def encode(self, value: float) -> int:
        if not isfinite(value):
            raise ValueError("cannot encode a non-finite value")
        return self.saturate(self._round_half_away_from_zero(value * self.scale))

    def decode(self, raw: int) -> float:
        return self.saturate(raw) / self.scale

    def multiply(self, left: int, right: int) -> int:
        product = left * right
        magnitude = abs(product)
        rounded = (magnitude + (self.scale // 2)) // self.scale
        shifted = rounded if product >= 0 else -rounded
        return self.saturate(shifted)


class FixedPointComplementaryFilter:
    """Saturating Q-format equivalent of :class:`ComplementaryFilter`.

    All calibrated parameters and sensor values are quantized at the pipeline
    boundary. Intermediate multiplication uses double width, rounds to nearest
    (ties away from zero), then saturates back to the configured signal format.
    This arithmetic contract should be copied by the HLS block and its tests.
    """

    def __init__(
        self,
        config: FusionConfig,
        q_format: QFormat | None = None,
    ) -> None:
        self.config = config
        self.q = q_format or QFormat()
        self._alpha = self.q.encode(config.alpha)
        self._one_minus_alpha = self.q.encode(1.0) - self._alpha
        self._torque_constant = self.q.encode(
            config.motor_torque_constant_nm_per_a
        )
        self._temperature_coefficient = self.q.encode(
            config.strain_temperature_coefficient_nm_per_c
        )
        self._current_offset = self.q.encode(config.current_offset_a)
        self._strain_offset = self.q.encode(config.strain_offset_nm)
        self._reference_temperature = self.q.encode(
            config.reference_temperature_c
        )
        self.reset()

    def reset(self) -> None:
        self._initialized = False
        self._previous_output = 0
        self._previous_current_torque = 0

    def _process_raw(
        self,
        strain_torque: int,
        phase_current: int,
        temperature: int,
    ) -> tuple[int, int, int]:
        temperature_delta = self.q.saturate(
            temperature - self._reference_temperature
        )
        temperature_correction = self.q.multiply(
            self._temperature_coefficient, temperature_delta
        )
        strain_corrected = self.q.saturate(
            strain_torque - self._strain_offset - temperature_correction
        )

        current_delta = self.q.saturate(phase_current - self._current_offset)
        current_torque = self.q.multiply(current_delta, self._torque_constant)

        if not self._initialized:
            fused = strain_corrected
            self._initialized = True
        else:
            high_pass_input = self.q.saturate(
                self._previous_output
                + current_torque
                - self._previous_current_torque
            )
            high_pass_term = self.q.multiply(self._alpha, high_pass_input)
            low_pass_term = self.q.multiply(
                self._one_minus_alpha, strain_corrected
            )
            fused = self.q.saturate(high_pass_term + low_pass_term)

        self._previous_output = fused
        self._previous_current_torque = current_torque
        return fused, strain_corrected, current_torque

    def process(self, sample: SensorSample) -> FusionOutput:
        values = (
            sample.timestamp_s,
            sample.strain_torque_nm,
            sample.phase_current_a,
            sample.encoder_position_rad,
            sample.temperature_c,
        )
        if not all(isfinite(value) for value in values):
            return FusionOutput(
                timestamp_s=sample.timestamp_s,
                torque_nm=self.q.decode(self._previous_output),
                strain_corrected_nm=0.0,
                current_torque_nm=0.0,
                encoder_position_rad=sample.encoder_position_rad,
                valid=False,
            )

        fused, strain_corrected, current_torque = self._process_raw(
            self.q.encode(sample.strain_torque_nm),
            self.q.encode(sample.phase_current_a),
            self.q.encode(sample.temperature_c),
        )
        return FusionOutput(
            timestamp_s=sample.timestamp_s,
            torque_nm=self.q.decode(fused),
            strain_corrected_nm=self.q.decode(strain_corrected),
            current_torque_nm=self.q.decode(current_torque),
            encoder_position_rad=sample.encoder_position_rad,
            valid=True,
        )
