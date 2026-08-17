# Force/Torque Sensor Fusion Coprocessor for Robotics

A dedicated real-time **companion chip** (FPGA IP first, ASIC later) for torque/force estimation and multi-sensor fusion — sold alongside existing motor controllers, not as a replacement for them.

> Companion fusion silicon between raw F/T sensing and the robot brain — programmable, control-loop-fast, and separate from the motor-control MCU.

## Docs

| File | Contents |
|---|---|
| [`SUMMARY.md`](SUMMARY.md) | Physics, product thesis, market, competition, customers, risks |
| [`THESIS_AND_HYPOTHESIS.md`](THESIS_AND_HYPOTHESIS.md) | FPGA-as-evidence thesis; 5–10× hypothesis; ASIC go/no-go exit criteria |
| [`TECHNICAL_BRIEF.md`](TECHNICAL_BRIEF.md) | Kria FPGA prototype architecture, algorithms, build steps, success criteria |
| [`docs/PHASE1_IMPLEMENTATION.md`](docs/PHASE1_IMPLEMENTATION.md) | Executable Stage 1 status, data contract, targets, and FPGA handoff |
| [`docs/AWS_F2.md`](docs/AWS_F2.md) | AWS F2 Vitis build/emulation workflow and measurement boundaries |
| [`docs/SPI_PROTOCOL.md`](docs/SPI_PROTOCOL.md) | Versioned companion-chip SPI wire format |

## The problem

Robot joints need clean torque/force inside 1–10 kHz control loops. Today that fusion either:

- runs as software on the same MCU as FOC (starved for cycles), or
- is locked inside a smart sensor black box (Bota, PaXini, ATI, …) you cannot tune.

Neither gives a programmable, high-bandwidth fusion layer *inside* the control loop.

## The product

An FPGA (then ASIC) coprocessor that:

1. Ingests strain/Hall torque, phase current, encoder, and temperature (IMU later)
2. Runs fixed-point complementary → Kalman estimation at hardware speed
3. Outputs low-latency F/T estimates over SPI (EtherCAT later)
4. Ships with an SDK so customers tune filters per application

## Validation bar (this phase)

Prototype on **AMD Kria KV260/KR260**. Beat shared-MCU software fusion by **~5–10×** in latency or update rate at equal/lower power on a real actuator. Miss that → no ASIC case yet.

See [`TECHNICAL_BRIEF.md`](TECHNICAL_BRIEF.md) for the full build plan.

## Roadmap

1. **Fusion coprocessor** (current) — additive, lowest requalification risk  
2. Multi-axis sync coprocessor  
3. Fused learned-model / control-loop SoC  

## Status

**Phase 1 started.** The repository now contains:

- A streaming floating-point complementary-filter reference
- A saturating Q16.16 model for future HLS/RTL parity
- Temperature compensation and motor-current torque conversion
- Deterministic synthetic sensor data, accuracy metrics, and tests
- A benchmark/vector-export CLI
- CSV calibration fitting and crossover tuning
- A tested SPI protocol codec with CRC-16
- Shared portable Q16.16 HLS compute core
- Separate Kria embedded and AWS F2 batch-kernel wrappers
- An XRT host that replays vectors and checks FPGA output against golden values

Run it:

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m ftfusion.cli --duration 2 --check
```

The next target is AWS F2 hardware emulation and hardware compilation. AWS
currently states that Vitis AFI generation is not supported on F2, so this
validates synthesis/timing/resources but does not yet execute the custom kernel
on live FPGA silicon. See
[`docs/AWS_F2.md`](docs/AWS_F2.md) and
[`docs/PHASE1_IMPLEMENTATION.md`](docs/PHASE1_IMPLEMENTATION.md) for measured
software-reference results and explicit measurement boundaries.
