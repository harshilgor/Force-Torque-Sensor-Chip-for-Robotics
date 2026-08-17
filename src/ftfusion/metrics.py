"""Accuracy and host-performance metrics for Phase 1 experiments."""

from dataclasses import dataclass
from math import sqrt
from time import perf_counter_ns
from typing import Callable, Sequence

import numpy as np
from numpy.typing import NDArray

from .models import FusionOutput, SensorSample


@dataclass(frozen=True, slots=True)
class AccuracyMetrics:
    rms_error_nm: float
    peak_error_nm: float


@dataclass(frozen=True, slots=True)
class HostTimingMetrics:
    samples: int
    elapsed_s: float
    mean_time_per_sample_us: float
    throughput_samples_per_s: float


def accuracy_metrics(
    estimates_nm: Sequence[float] | NDArray[np.float64],
    reference_nm: Sequence[float] | NDArray[np.float64],
) -> AccuracyMetrics:
    estimate = np.asarray(estimates_nm, dtype=np.float64)
    reference = np.asarray(reference_nm, dtype=np.float64)
    if estimate.shape != reference.shape or estimate.size == 0:
        raise ValueError("estimate and reference must have the same non-zero shape")
    error = estimate - reference
    return AccuracyMetrics(
        rms_error_nm=float(sqrt(float(np.mean(np.square(error))))),
        peak_error_nm=float(np.max(np.abs(error))),
    )


def time_stream(
    processor: Callable[[SensorSample], FusionOutput],
    samples: Sequence[SensorSample],
) -> tuple[list[FusionOutput], HostTimingMetrics]:
    """Measure host execution only; this is not an FPGA latency claim."""

    if not samples:
        raise ValueError("samples must not be empty")
    start_ns = perf_counter_ns()
    outputs = [processor(sample) for sample in samples]
    elapsed_s = (perf_counter_ns() - start_ns) / 1_000_000_000.0
    return outputs, HostTimingMetrics(
        samples=len(samples),
        elapsed_s=elapsed_s,
        mean_time_per_sample_us=elapsed_s * 1_000_000.0 / len(samples),
        throughput_samples_per_s=len(samples) / elapsed_s,
    )
