"""Fit calibration parameters and tune the complementary crossover from CSV."""

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from .calibration import (
    fit_calibration,
    load_calibration_csv,
    tune_crossover,
)
from .complementary import FusionConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calibrate an MVP joint torque channel from a reference log."
    )
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--sample-rate", type=float, default=10_000.0)
    parser.add_argument("--crossover", type=float, default=30.0)
    parser.add_argument(
        "--tune-crossover",
        action="store_true",
        help="Sweep crossover candidates and choose minimum fused RMS error.",
    )
    parser.add_argument("--output", type=Path, help="Optional calibration JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dataset = load_calibration_csv(args.input_csv)
    base = FusionConfig(
        sample_rate_hz=args.sample_rate,
        crossover_hz=args.crossover,
    )
    calibration = fit_calibration(dataset, base)
    config = calibration.config
    tuning_report = None
    if args.tune_crossover:
        tuning = tune_crossover(dataset, config)
        config = replace(config, crossover_hz=tuning.crossover_hz)
        tuning_report = {
            "selected_crossover_hz": tuning.crossover_hz,
            "fused_rms_error_nm": tuning.accuracy.rms_error_nm,
            "fused_peak_error_nm": tuning.accuracy.peak_error_nm,
            "evaluated_candidates": tuning.evaluated_candidates,
        }

    report = {
        "config": asdict(config),
        "calibration_fit": {
            "strain_rms_error_nm": calibration.strain_error.rms_error_nm,
            "strain_peak_error_nm": calibration.strain_error.peak_error_nm,
            "current_rms_error_nm": calibration.current_error.rms_error_nm,
            "current_peak_error_nm": calibration.current_error.peak_error_nm,
        },
        "crossover_tuning": tuning_report,
        "samples": len(dataset.samples),
    }
    encoded = json.dumps(report, indent=2)
    print(encoded)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
        print(f"Wrote calibration to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
