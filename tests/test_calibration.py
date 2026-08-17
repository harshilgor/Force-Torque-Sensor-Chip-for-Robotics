import csv
from dataclasses import replace

import numpy as np
import pytest

from ftfusion.calibration import (
    CalibrationDataset,
    fit_calibration,
    load_calibration_csv,
    tune_crossover,
)
from ftfusion.complementary import FusionConfig
from ftfusion.models import SensorSample
from ftfusion.synthetic import generate_synthetic_run


def controlled_dataset(sample_count: int = 1_000) -> CalibrationDataset:
    time_s = np.arange(sample_count, dtype=np.float64) / 1_000.0
    reference = 0.8 * np.sin(2.0 * np.pi * 2.0 * time_s)
    temperature = 25.0 + 5.0 * np.sin(2.0 * np.pi * 0.37 * time_s)
    strain_offset = 0.07
    temperature_coefficient = 0.004
    torque_constant = 0.15
    current_offset = -0.08
    samples = [
        SensorSample(
            timestamp_s=float(time_s[index]),
            strain_torque_nm=float(
                reference[index]
                + strain_offset
                + temperature_coefficient * (temperature[index] - 25.0)
            ),
            phase_current_a=float(
                reference[index] / torque_constant + current_offset
            ),
            encoder_position_rad=0.0,
            temperature_c=float(temperature[index]),
        )
        for index in range(sample_count)
    ]
    return CalibrationDataset(samples, reference)


def test_fit_calibration_recovers_known_sensor_parameters() -> None:
    dataset = controlled_dataset()
    result = fit_calibration(
        dataset,
        FusionConfig(sample_rate_hz=1_000.0, crossover_hz=20.0),
    )
    assert result.config.motor_torque_constant_nm_per_a == pytest.approx(0.15)
    assert result.config.current_offset_a == pytest.approx(-0.08)
    assert (
        result.config.strain_temperature_coefficient_nm_per_c
        == pytest.approx(0.004)
    )
    assert result.strain_error.rms_error_nm < 1e-12
    assert result.current_error.rms_error_nm < 1e-12


def test_load_calibration_csv_accepts_reference_column(tmp_path) -> None:
    dataset = controlled_dataset(sample_count=10)
    path = tmp_path / "calibration.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "timestamp_s",
                "strain_torque_nm",
                "phase_current_a",
                "encoder_position_rad",
                "temperature_c",
                "reference_torque_nm",
            )
        )
        for sample, reference in zip(
            dataset.samples,
            dataset.reference_torque_nm,
            strict=True,
        ):
            writer.writerow(
                (
                    sample.timestamp_s,
                    sample.strain_torque_nm,
                    sample.phase_current_a,
                    sample.encoder_position_rad,
                    sample.temperature_c,
                    reference,
                )
            )
    loaded = load_calibration_csv(path)
    assert loaded.samples == dataset.samples
    np.testing.assert_allclose(
        loaded.reference_torque_nm,
        dataset.reference_torque_nm,
    )


def test_tune_crossover_returns_best_supplied_candidate() -> None:
    config = FusionConfig()
    run = generate_synthetic_run(config, duration_s=0.5)
    dataset = CalibrationDataset(run.samples, run.true_torque_nm)
    result = tune_crossover(dataset, config, candidates_hz=(5.0, 30.0, 100.0))
    assert result.crossover_hz in (5.0, 30.0, 100.0)
    assert result.evaluated_candidates == 3
    assert result.accuracy.rms_error_nm > 0


def test_calibration_rejects_unobservable_temperature() -> None:
    dataset = controlled_dataset(sample_count=20)
    constant_temperature = CalibrationDataset(
        [
            replace(sample, temperature_c=25.0)
            for sample in dataset.samples
        ],
        dataset.reference_torque_nm,
    )
    with pytest.raises(ValueError, match="temperature excitation"):
        fit_calibration(constant_temperature)
