"""Command-line benchmark and HLS-vector generator."""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from .complementary import ComplementaryFilter, FusionConfig
from .fixed_point import FixedPointComplementaryFilter, QFormat
from .metrics import accuracy_metrics, time_stream
from .synthetic import generate_synthetic_run


def _write_vectors(
    path: Path,
    samples: list,
    truth: np.ndarray,
    floating_outputs: list,
    fixed_outputs: list,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
                "floating_fused_nm",
                "fixed_fused_nm",
            )
        )
        for sample, reference, floating, fixed in zip(
            samples, truth, floating_outputs, fixed_outputs, strict=True
        ):
            writer.writerow(
                (
                    sample.timestamp_s,
                    sample.strain_torque_nm,
                    sample.phase_current_a,
                    sample.encoder_position_rad,
                    sample.temperature_c,
                    reference,
                    floating.torque_nm,
                    fixed.torque_nm,
                )
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Phase 1 complementary-filter reference benchmark."
    )
    parser.add_argument("--sample-rate", type=float, default=10_000.0)
    parser.add_argument("--crossover", type=float, default=30.0)
    parser.add_argument("--duration", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--vectors",
        type=Path,
        help="Optional CSV output for future HLS/RTL testbenches.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional JSON output for a repeatable experiment record.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail unless fusion improves both channels and fixed-point parity passes.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = FusionConfig(
        sample_rate_hz=args.sample_rate,
        crossover_hz=args.crossover,
    )
    run = generate_synthetic_run(config, duration_s=args.duration, seed=args.seed)

    floating_filter = ComplementaryFilter(config)
    floating_outputs, floating_timing = time_stream(
        floating_filter.process, run.samples
    )
    fixed_filter = FixedPointComplementaryFilter(config, QFormat(32, 16))
    fixed_outputs, fixed_timing = time_stream(fixed_filter.process, run.samples)

    floating_estimate = np.asarray(
        [output.torque_nm for output in floating_outputs]
    )
    fixed_estimate = np.asarray([output.torque_nm for output in fixed_outputs])
    strain_estimate = np.asarray(
        [output.strain_corrected_nm for output in floating_outputs]
    )
    current_estimate = np.asarray(
        [output.current_torque_nm for output in floating_outputs]
    )

    floating_accuracy = accuracy_metrics(
        floating_estimate, run.true_torque_nm
    )
    fixed_accuracy = accuracy_metrics(fixed_estimate, run.true_torque_nm)
    strain_accuracy = accuracy_metrics(strain_estimate, run.true_torque_nm)
    current_accuracy = accuracy_metrics(current_estimate, run.true_torque_nm)
    fixed_delta = accuracy_metrics(fixed_estimate, floating_estimate)

    report = {
        "configuration": {
            "sample_rate_hz": config.sample_rate_hz,
            "crossover_hz": config.crossover_hz,
            "alpha": config.alpha,
            "samples": len(run.samples),
            "q_format": "Q16.16",
        },
        "accuracy_rms_nm": {
            "strain_temperature_corrected": strain_accuracy.rms_error_nm,
            "current_derived": current_accuracy.rms_error_nm,
            "floating_fused": floating_accuracy.rms_error_nm,
            "fixed_fused": fixed_accuracy.rms_error_nm,
            "fixed_vs_floating": fixed_delta.rms_error_nm,
        },
        "fixed_vs_floating_peak_error_nm": fixed_delta.peak_error_nm,
        "host_reference_timing": {
            "floating_mean_us_per_sample": (
                floating_timing.mean_time_per_sample_us
            ),
            "floating_throughput_samples_per_s": (
                floating_timing.throughput_samples_per_s
            ),
            "fixed_mean_us_per_sample": fixed_timing.mean_time_per_sample_us,
            "fixed_throughput_samples_per_s": (
                fixed_timing.throughput_samples_per_s
            ),
            "warning": (
                "Host timing validates the harness only; it is not FPGA "
                "end-to-end latency or a C2000 comparison."
            ),
        },
    }
    report["acceptance"] = {
        "fusion_beats_strain": (
            floating_accuracy.rms_error_nm < strain_accuracy.rms_error_nm
        ),
        "fusion_beats_current": (
            floating_accuracy.rms_error_nm < current_accuracy.rms_error_nm
        ),
        "fixed_peak_error_below_0_001_nm": (
            fixed_delta.peak_error_nm < 0.001
        ),
    }
    encoded_report = json.dumps(report, indent=2)
    print(encoded_report)

    if args.vectors:
        _write_vectors(
            args.vectors,
            run.samples,
            run.true_torque_nm,
            floating_outputs,
            fixed_outputs,
        )
        print(f"Wrote {len(run.samples)} vectors to {args.vectors}")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded_report + "\n", encoding="utf-8")
        print(f"Wrote benchmark report to {args.report}")

    return 0 if not args.check or all(report["acceptance"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
