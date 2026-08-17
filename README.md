# Force/Torque Sensor Fusion Coprocessor for Robotics

A dedicated real-time **companion chip** (FPGA IP first, ASIC later) for torque/force estimation and multi-sensor fusion — sold alongside existing motor controllers, not as a replacement for them.

> Companion fusion silicon between raw F/T sensing and the robot brain — programmable, control-loop-fast, and separate from the motor-control MCU.

## Docs

| File | Contents |
|---|---|
| [`SUMMARY.md`](SUMMARY.md) | Physics, product thesis, market, competition, customers, risks |
| [`TECHNICAL_BRIEF.md`](TECHNICAL_BRIEF.md) | Kria FPGA prototype architecture, algorithms, build steps, success criteria |

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

Documentation and technical plan only. FPGA prototype not started.
