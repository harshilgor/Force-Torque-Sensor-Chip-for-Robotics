from math import isclose

import numpy as np
import pytest

from ftfusion import (
    ComplementaryFilter,
    FixedPointComplementaryFilter,
    FusionConfig,
    QFormat,
    SensorSample,
)
from ftfusion.metrics import accuracy_metrics
from ftfusion.synthetic import generate_synthetic_run


def sample(
    *,
    timestamp_s: float = 0.0,
    strain_torque_nm: float = 0.0,
    phase_current_a: float = 0.0,
    temperature_c: float = 25.0,
) -> SensorSample:
    return SensorSample(
        timestamp_s=timestamp_s,
        strain_torque_nm=strain_torque_nm,
        phase_current_a=phase_current_a,
        encoder_position_rad=0.0,
        temperature_c=temperature_c,
    )


def test_rejects_invalid_filter_configuration() -> None:
    with pytest.raises(ValueError):
        FusionConfig(sample_rate_hz=0.0)
    with pytest.raises(ValueError):
        FusionConfig(sample_rate_hz=1_000.0, crossover_hz=500.0)


def test_temperature_compensation_removes_calibrated_drift() -> None:
    config = FusionConfig(
        strain_temperature_coefficient_nm_per_c=0.01,
        reference_temperature_c=25.0,
    )
    output = ComplementaryFilter(config).process(
        sample(strain_torque_nm=1.1, temperature_c=35.0)
    )
    assert output.strain_corrected_nm == pytest.approx(1.0)
    assert output.torque_nm == pytest.approx(1.0)


def test_current_step_passes_immediately_then_decays_to_strain() -> None:
    config = FusionConfig(
        sample_rate_hz=10_000.0,
        crossover_hz=30.0,
        motor_torque_constant_nm_per_a=1.0,
    )
    filter_model = ComplementaryFilter(config)
    filter_model.process(sample())
    step = filter_model.process(
        sample(timestamp_s=0.0001, phase_current_a=1.0)
    )
    assert step.torque_nm == pytest.approx(config.alpha)

    output = step
    for index in range(1_000):
        output = filter_model.process(
            sample(timestamp_s=(index + 2) / config.sample_rate_hz, phase_current_a=1.0)
        )
    assert abs(output.torque_nm) < 1e-8


def test_non_finite_input_is_invalid_and_holds_last_estimate() -> None:
    filter_model = ComplementaryFilter(FusionConfig())
    valid = filter_model.process(sample(strain_torque_nm=0.75))
    invalid = filter_model.process(sample(timestamp_s=0.1, strain_torque_nm=float("nan")))
    assert not invalid.valid
    assert invalid.torque_nm == valid.torque_nm


def test_fixed_point_tracks_floating_reference() -> None:
    config = FusionConfig()
    run = generate_synthetic_run(config, duration_s=0.5)
    floating = ComplementaryFilter(config)
    fixed = FixedPointComplementaryFilter(config, QFormat(32, 16))
    floating_values = np.asarray(
        [floating.process(value).torque_nm for value in run.samples]
    )
    fixed_values = np.asarray(
        [fixed.process(value).torque_nm for value in run.samples]
    )
    difference = accuracy_metrics(fixed_values, floating_values)
    assert difference.rms_error_nm < 0.001
    assert difference.peak_error_nm < 0.003


def test_fusion_improves_synthetic_channel_accuracy() -> None:
    config = FusionConfig()
    run = generate_synthetic_run(config, duration_s=2.0)
    filter_model = ComplementaryFilter(config)
    outputs = [filter_model.process(value) for value in run.samples]

    fused = np.asarray([value.torque_nm for value in outputs])
    strain = np.asarray([value.strain_corrected_nm for value in outputs])
    current = np.asarray([value.current_torque_nm for value in outputs])

    fused_error = accuracy_metrics(fused, run.true_torque_nm).rms_error_nm
    strain_error = accuracy_metrics(strain, run.true_torque_nm).rms_error_nm
    current_error = accuracy_metrics(current, run.true_torque_nm).rms_error_nm
    assert fused_error < strain_error
    assert fused_error < current_error


def test_q_format_saturates_and_rounds_symmetrically() -> None:
    q_format = QFormat(total_bits=8, fractional_bits=4)
    assert q_format.encode(100.0) == q_format.maximum_raw
    assert q_format.encode(-100.0) == q_format.minimum_raw
    assert isclose(q_format.decode(q_format.encode(0.5)), 0.5)
    assert q_format.encode(0.03125) == 1
    assert q_format.encode(-0.03125) == -1
