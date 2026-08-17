"""Streaming floating-point reference for the Stage 1 fusion pipeline."""

from dataclasses import dataclass
from math import exp, isfinite, pi
from typing import Iterable

from .models import FusionOutput, SensorSample


@dataclass(frozen=True, slots=True)
class FusionConfig:
    """Calibrated parameters for a single joint torque channel."""

    sample_rate_hz: float = 10_000.0
    crossover_hz: float = 30.0
    motor_torque_constant_nm_per_a: float = 0.12
    current_offset_a: float = 0.0
    strain_offset_nm: float = 0.0
    strain_temperature_coefficient_nm_per_c: float = 0.002
    reference_temperature_c: float = 25.0

    def __post_init__(self) -> None:
        values = (
            self.sample_rate_hz,
            self.crossover_hz,
            self.motor_torque_constant_nm_per_a,
            self.current_offset_a,
            self.strain_offset_nm,
            self.strain_temperature_coefficient_nm_per_c,
            self.reference_temperature_c,
        )
        if not all(isfinite(value) for value in values):
            raise ValueError("fusion parameters must be finite")
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if not 0 < self.crossover_hz < self.sample_rate_hz / 2:
            raise ValueError("crossover_hz must be between 0 and Nyquist")

    @property
    def alpha(self) -> float:
        """Matched one-pole coefficient for the requested crossover."""

        return exp(-2.0 * pi * self.crossover_hz / self.sample_rate_hz)


class ComplementaryFilter:
    """Fuse low-frequency strain torque with high-frequency current torque.

    The recurrence is:

        y[n] = alpha * (y[n-1] + i[n] - i[n-1])
             + (1 - alpha) * s[n]

    where ``s`` is temperature-corrected strain torque and ``i`` is
    current-derived torque. At steady state the estimate converges to strain;
    fast current changes pass through immediately.
    """

    def __init__(self, config: FusionConfig) -> None:
        self.config = config
        self.reset()

    def reset(self) -> None:
        self._initialized = False
        self._previous_output_nm = 0.0
        self._previous_current_torque_nm = 0.0

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
                torque_nm=self._previous_output_nm,
                strain_corrected_nm=0.0,
                current_torque_nm=0.0,
                encoder_position_rad=sample.encoder_position_rad,
                valid=False,
            )

        strain_corrected = sample.strain_torque_nm - self.config.strain_offset_nm - (
            self.config.strain_temperature_coefficient_nm_per_c
            * (sample.temperature_c - self.config.reference_temperature_c)
        )
        current_torque = (
            sample.phase_current_a - self.config.current_offset_a
        ) * self.config.motor_torque_constant_nm_per_a

        if not self._initialized:
            fused = strain_corrected
            self._initialized = True
        else:
            alpha = self.config.alpha
            fused = alpha * (
                self._previous_output_nm
                + current_torque
                - self._previous_current_torque_nm
            ) + (1.0 - alpha) * strain_corrected

        self._previous_output_nm = fused
        self._previous_current_torque_nm = current_torque

        return FusionOutput(
            timestamp_s=sample.timestamp_s,
            torque_nm=fused,
            strain_corrected_nm=strain_corrected,
            current_torque_nm=current_torque,
            encoder_position_rad=sample.encoder_position_rad,
            valid=True,
        )


def fuse_samples(
    samples: Iterable[SensorSample], config: FusionConfig
) -> list[FusionOutput]:
    """Run a synchronized sample stream through a fresh filter instance."""

    filter_model = ComplementaryFilter(config)
    return [filter_model.process(sample) for sample in samples]
