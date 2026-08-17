# Phase 1 Implementation

## Current milestone

The first executable milestone freezes the Stage 1 algorithm and arithmetic
contract before tying it to a specific ADC, encoder, or Kria carrier.

Implemented:

- Synchronized MVP sensor frame in engineering units
- Strain temperature correction
- Current-to-torque conversion using calibrated motor `Kt`
- Streaming one-pole complementary filter
- Floating-point correctness reference
- Saturating Q16.16 model for HLS/RTL parity
- Deterministic synthetic joint/load generator
- Accuracy and host-harness timing metrics
- CSV vector export for a future HLS/RTL testbench
- Automated behavioral and fixed-point parity tests
- CSV calibration fitting for strain offset, thermal drift, motor Kt, and
  current offset
- Logged-data crossover tuning
- Versioned SPI output/config codec with CRC-16
- Portable Q16.16 C++ HLS kernel, C testbench, and Vitis HLS script

Not yet claimed:

- FPGA synthesis, timing closure, resource usage, or PL power
- ADC/encoder electrical interfaces
- Physical end-to-end latency
- C2000 comparison
- Accuracy against a calibrated physical torque reference

## Frozen initial targets

| Metric | Initial target |
|---|---:|
| Sample/output rate | 10 kHz minimum |
| Raw-to-fused latency | <50 µs |
| FPGA advantage | 5–10× latency or update-rate improvement |
| FPGA power | Equal to or below the shared-MCU baseline |
| Fixed-point format | Signed saturating Q16.16 |
| Complementary crossover | 30 Hz (runtime calibration target) |

The update rate and latency targets are acceptance criteria, not measured
results. Physical latency must be measured from an input GPIO strobe to an
output-valid/SPI event with an oscilloscope or logic analyzer.

## Pipeline contract

One input sample contains:

| Field | Unit |
|---|---|
| Timestamp | seconds |
| Strain torque | N·m |
| Phase current | A |
| Encoder position | rad |
| Temperature | °C |

The Stage 1 recurrence is:

```text
strain_corrected = strain - temp_coefficient * (temperature - temp_reference)
current_torque   = (current - current_offset) * Kt

y[n] = alpha * (y[n-1] + current_torque[n] - current_torque[n-1])
     + (1 - alpha) * strain_corrected[n]
```

`alpha = exp(-2π × crossover_hz / sample_rate_hz)`.

At DC, the estimate converges to the strain channel. Fast torque changes from
the current-derived channel pass through before decaying toward strain.

## Run locally

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m ftfusion.cli --duration 2 --check
```

Generate deterministic vectors for the future HLS testbench:

```powershell
python -m ftfusion.cli --duration 2 --vectors artifacts/hls_vectors.csv
```

Save a machine-readable experiment report:

```powershell
python -m ftfusion.cli --duration 2 --check `
  --report artifacts/synthetic_report.json
```

Calibrate and tune from a physical-unit CSV containing the input fields plus
`reference_torque_nm`:

```powershell
python -m ftfusion.calibration_cli data/calibration.csv `
  --sample-rate 10000 --tune-crossover `
  --output artifacts/calibration.json
```

The synthetic vector export has the same schema and can exercise this flow
before real logs exist.

## Initial simulated result

Using the deterministic 20,000-sample synthetic run at 10 kHz:

| Signal/model | RMS error |
|---|---:|
| Temperature-corrected strain | 0.034736 N·m |
| Current-derived torque | 0.161360 N·m |
| Floating-point fused | 0.012344 N·m |
| Q16.16 fused | 0.012342 N·m |
| Q16.16 vs. float, peak difference | 0.000117 N·m |

This validates the model and chosen precision against synthetic data only. It
does not validate the product's 5–10× business threshold.

## Next implementation slice

Phase 1 now has two target wrappers around `hls/common/ftfusion_core.hpp`:

1. `hls/aws_f2/` — PCIe batch kernel with `m_axi` buffers, XRT host, and `v++`
   build/emulation flow. Follow `docs/AWS_F2.md`.
2. `hls/kria/` — retained embedded HLS target for a future physical board.

Immediate cloud sequence:

1. Run the Python tests and export golden vectors locally.
2. Configure an AWS FPGA Developer environment from the `aws-fpga` `f2`
   branch and install/source XRT.
3. Run `make run TARGET=hw_emu PLATFORM=$SHELL_EMU_VERSION`.
4. Run `make build TARGET=hw PLATFORM=$SHELL_EMU_VERSION`.
5. Archive parity, initiation interval, timing, and utilization reports.

AWS currently documents that Vitis AFI generation is not supported on F2.
Accordingly, this sequence provides hardware emulation and implementation
feedback, not execution of this custom kernel on live F2 silicon.

The board-specific ingest block cannot be finalized until the exact Kria board,
carrier, ADC, encoder type, and voltage/interface constraints are known.

## Hardware-free completion boundary

Work that can be completed without a physical FPGA:

- Reference algorithms, calibration, tuning, fault behavior, and protocol
- Fixed-point arithmetic specification and golden vectors
- Shared HLS source, F2 `hw_emu`, and F2 hardware compilation/reports
- Host SDK/codec and software benchmark automation

Work that fundamentally requires hardware:

- Execution of a custom accelerator on FPGA silicon (until AWS supports the
  required F2 Vitis AFI path or another supported cloud target is selected)
- Real ADC/encoder electrical bring-up and synchronization
- Scope-verified input-to-output latency
- PL rail power and thermal measurements
- Signal-integrity and maximum SPI-clock validation
- Real actuator accuracy and C2000 head-to-head testing
