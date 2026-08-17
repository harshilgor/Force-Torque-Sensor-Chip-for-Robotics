"""Deterministic synthetic joint data for development before bench hardware."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .complementary import FusionConfig
from .models import SensorSample


@dataclass(frozen=True, slots=True)
class SyntheticRun:
    samples: list[SensorSample]
    true_torque_nm: NDArray[np.float64]


def generate_synthetic_run(
    config: FusionConfig,
    duration_s: float = 2.0,
    seed: int = 7,
) -> SyntheticRun:
    """Generate a repeatable stream with noise, bias, dynamics, and thermal drift."""

    if duration_s <= 0:
        raise ValueError("duration_s must be positive")

    sample_count = int(round(duration_s * config.sample_rate_hz))
    if sample_count < 2:
        raise ValueError("duration is too short for the configured sample rate")

    rng = np.random.default_rng(seed)
    time_s = np.arange(sample_count, dtype=np.float64) / config.sample_rate_hz

    low_frequency_load = (
        0.75 * np.sin(2.0 * np.pi * 1.3 * time_s)
        + 0.20 * np.sin(2.0 * np.pi * 4.0 * time_s)
    )
    high_frequency_load = 0.08 * np.sin(2.0 * np.pi * 180.0 * time_s)
    contact_step = np.where(time_s >= duration_s * 0.45, 0.35, 0.0)
    release_step = np.where(time_s >= duration_s * 0.72, -0.22, 0.0)
    true_torque = (
        low_frequency_load + high_frequency_load + contact_step + release_step
    )

    temperature_c = (
        config.reference_temperature_c
        + 4.0 * np.sin(2.0 * np.pi * 0.08 * time_s)
        + 0.7 * time_s / duration_s
    )
    strain_noise = rng.normal(0.0, 0.035, sample_count)
    strain_torque = (
        true_torque
        + config.strain_offset_nm
        + config.strain_temperature_coefficient_nm_per_c
        * (temperature_c - config.reference_temperature_c)
        + strain_noise
    )

    current_bias = (
        0.10
        + 0.06 * np.sin(2.0 * np.pi * 0.25 * time_s)
        + 0.02 * temperature_c / config.reference_temperature_c
    )
    current_noise = rng.normal(0.0, 0.012, sample_count)
    current_torque = true_torque + current_bias + current_noise
    phase_current_a = (
        current_torque / config.motor_torque_constant_nm_per_a
        + config.current_offset_a
    )

    encoder_position = 0.25 * np.sin(2.0 * np.pi * 0.7 * time_s)
    samples = [
        SensorSample(
            timestamp_s=float(time_s[index]),
            strain_torque_nm=float(strain_torque[index]),
            phase_current_a=float(phase_current_a[index]),
            encoder_position_rad=float(encoder_position[index]),
            temperature_c=float(temperature_c[index]),
        )
        for index in range(sample_count)
    ]
    return SyntheticRun(samples=samples, true_torque_nm=true_torque)
