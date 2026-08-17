"""Offline calibration and crossover tuning from synchronized torque logs."""

import csv
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

import numpy as np
from numpy.typing import NDArray

from .complementary import FusionConfig, fuse_samples
from .metrics import AccuracyMetrics, accuracy_metrics
from .models import SensorSample


@dataclass(frozen=True, slots=True)
class CalibrationDataset:
    samples: list[SensorSample]
    reference_torque_nm: NDArray[np.float64]

    def __post_init__(self) -> None:
        if not self.samples:
            raise ValueError("calibration dataset must not be empty")
        if len(self.samples) != len(self.reference_torque_nm):
            raise ValueError("sample and reference lengths must match")
        if not np.all(np.isfinite(self.reference_torque_nm)):
            raise ValueError("reference torque must be finite")


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    config: FusionConfig
    strain_error: AccuracyMetrics
    current_error: AccuracyMetrics


@dataclass(frozen=True, slots=True)
class TuningResult:
    crossover_hz: float
    accuracy: AccuracyMetrics
    evaluated_candidates: int


_REQUIRED_COLUMNS = {
    "timestamp_s",
    "strain_torque_nm",
    "phase_current_a",
    "encoder_position_rad",
    "temperature_c",
}


def load_calibration_csv(path: str | Path) -> CalibrationDataset:
    """Load physical-unit data; reference may be named reference or true torque."""

    samples: list[SensorSample] = []
    references: list[float] = []
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        columns = set(reader.fieldnames or ())
        missing = _REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"missing CSV columns: {sorted(missing)}")
        reference_column = (
            "reference_torque_nm"
            if "reference_torque_nm" in columns
            else "true_torque_nm"
            if "true_torque_nm" in columns
            else None
        )
        if reference_column is None:
            raise ValueError(
                "CSV needs reference_torque_nm (or true_torque_nm for simulation)"
            )
        for row in reader:
            samples.append(
                SensorSample(
                    timestamp_s=float(row["timestamp_s"]),
                    strain_torque_nm=float(row["strain_torque_nm"]),
                    phase_current_a=float(row["phase_current_a"]),
                    encoder_position_rad=float(row["encoder_position_rad"]),
                    temperature_c=float(row["temperature_c"]),
                )
            )
            references.append(float(row[reference_column]))
    return CalibrationDataset(
        samples=samples,
        reference_torque_nm=np.asarray(references, dtype=np.float64),
    )


def fit_calibration(
    dataset: CalibrationDataset,
    base_config: FusionConfig | None = None,
) -> CalibrationResult:
    """Fit strain offset/thermal drift and motor Kt/current offset.

    The calibration log must contain enough independent temperature and current
    excitation to make both two-parameter least-squares problems observable.
    """

    base = base_config or FusionConfig()
    strain = np.asarray(
        [sample.strain_torque_nm for sample in dataset.samples],
        dtype=np.float64,
    )
    current = np.asarray(
        [sample.phase_current_a for sample in dataset.samples],
        dtype=np.float64,
    )
    temperature = np.asarray(
        [sample.temperature_c for sample in dataset.samples],
        dtype=np.float64,
    )
    reference = dataset.reference_torque_nm
    reference_temperature = float(np.median(temperature))

    thermal_design = np.column_stack(
        (
            np.ones(len(temperature)),
            temperature - reference_temperature,
        )
    )
    if np.linalg.matrix_rank(thermal_design) < 2:
        raise ValueError("temperature excitation is insufficient for calibration")
    strain_offset, temperature_coefficient = np.linalg.lstsq(
        thermal_design,
        strain - reference,
        rcond=None,
    )[0]

    current_design = np.column_stack((current, np.ones(len(current))))
    if np.linalg.matrix_rank(current_design) < 2:
        raise ValueError("current excitation is insufficient for calibration")
    torque_constant, intercept = np.linalg.lstsq(
        current_design,
        reference,
        rcond=None,
    )[0]
    if abs(torque_constant) < 1e-12:
        raise ValueError("fitted motor torque constant is effectively zero")
    current_offset = -intercept / torque_constant

    config = replace(
        base,
        motor_torque_constant_nm_per_a=float(torque_constant),
        current_offset_a=float(current_offset),
        strain_offset_nm=float(strain_offset),
        strain_temperature_coefficient_nm_per_c=float(
            temperature_coefficient
        ),
        reference_temperature_c=reference_temperature,
    )
    strain_prediction = strain - strain_offset - temperature_coefficient * (
        temperature - reference_temperature
    )
    current_prediction = (current - current_offset) * torque_constant
    return CalibrationResult(
        config=config,
        strain_error=accuracy_metrics(strain_prediction, reference),
        current_error=accuracy_metrics(current_prediction, reference),
    )


def tune_crossover(
    dataset: CalibrationDataset,
    calibrated_config: FusionConfig,
    candidates_hz: Iterable[float] | None = None,
) -> TuningResult:
    """Select the candidate crossover with minimum reference RMS error."""

    if candidates_hz is None:
        upper = min(500.0, calibrated_config.sample_rate_hz * 0.2)
        candidates = np.geomspace(1.0, upper, 48)
    else:
        candidates = np.asarray(list(candidates_hz), dtype=np.float64)
    if candidates.size == 0 or not np.all(np.isfinite(candidates)):
        raise ValueError("crossover candidates must be finite and non-empty")

    best: TuningResult | None = None
    for crossover in candidates:
        try:
            config = replace(calibrated_config, crossover_hz=float(crossover))
        except ValueError:
            continue
        outputs = fuse_samples(dataset.samples, config)
        estimate = [output.torque_nm for output in outputs]
        candidate = TuningResult(
            crossover_hz=float(crossover),
            accuracy=accuracy_metrics(
                estimate, dataset.reference_torque_nm
            ),
            evaluated_candidates=0,
        )
        if best is None or candidate.accuracy.rms_error_nm < best.accuracy.rms_error_nm:
            best = candidate
    if best is None:
        raise ValueError("no crossover candidate falls below Nyquist")
    return replace(best, evaluated_candidates=len(candidates))
