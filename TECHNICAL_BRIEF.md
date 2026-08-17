# Torque/Force Fusion Coprocessor — Technical Build Brief

## 0. Goal of This Phase

The current execution target is **AWS EC2 F2 Vitis hardware emulation and
hardware compilation**, because a physical Kria board is not yet available.
This cloud stage validates fixed-point parity, synthesis, timing closure,
initiation interval, and estimated resource cost.

The eventual product-validation goal remains a working Kria KV260/KR260
prototype that proves: **hardware-accelerated torque/force estimation at higher
update rate and lower latency than software fusion on a shared MCU, at
comparable or lower power.**

This artifact validates or kills the business case. Nothing here needs to be production-hardened yet.

AWS batch/DMA timing is not equivalent to physical raw-signal-to-fused-output
latency. AWS currently documents that Vitis AFI generation is not supported on
F2, so the current cloud flow must not be represented as live FPGA execution.
See [`docs/AWS_F2.md`](docs/AWS_F2.md).

### Success criteria (fill in before coding — these are the benchmark targets)

| Metric | Example target | Notes |
|---|---|---|
| Update rate | 10 kHz+ fused torque output | vs. typical 1–2 kHz on a shared MCU loop |
| End-to-end latency | <50 µs raw → fused output | Measure with scope/logic analyzer, not only internal timestamps |
| Estimation accuracy | RMS error vs. calibrated reference torque | Define reference method on the test rig |
| Power | Fusion logic only | Isolate from the rest of the SoC |

Business go/no-go bar (from product brief): **5–10×** improvement in latency or update rate at equal or lower power vs. shared-MCU software fusion.

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Kria KV260/KR260                      │
│  ┌──────────────┐        ┌───────────────────────────┐  │
│  │   PS (ARM)   │◄──────►│      PL (FPGA fabric)      │  │
│  │  Linux/RTOS  │  AXI   │                             │  │
│  │  - config    │        │  ┌───────────────────────┐  │  │
│  │  - telemetry │        │  │ Sensor Ingest Block   │  │  │
│  │  - SDK/API   │        │  │ - ADC interface(s)    │  │  │
│  └──────────────┘        │  │ - encoder decoder     │  │  │
│                           │  │ - SPI/I2C IMU intf    │  │  │
│                           │  └──────────┬────────────┘  │  │
│                           │             ▼                │  │
│                           │  ┌───────────────────────┐  │  │
│                           │  │ Fusion/Estimation Core │  │  │
│                           │  │ - Kalman/complementary │  │  │
│                           │  │   filter (fixed-point) │  │  │
│                           │  │ - torque-from-current  │  │  │
│                           │  │   cross-check          │  │  │
│                           │  │ - temp compensation    │  │  │
│                           │  └──────────┬────────────┘  │  │
│                           │             ▼                │  │
│                           │  ┌───────────────────────┐  │  │
│                           │  │ Output Interface       │  │  │
│                           │  │ - SPI slave to host MCU│  │  │
│                           │  │ - (later: EtherCAT)    │  │  │
│                           │  └───────────────────────┘  │  │
│                           └───────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
        ▲                                          │
        │ raw sensor signals                        │ fused torque/force estimate
        │                                            ▼
┌───────────────┐                          ┌──────────────────┐
│ Strain gauge / │                          │ Host motor        │
│ Hall-effect     │                          │ controller (MCU)  │
│ torque sensor + │                          │ running FOC       │
│ current shunt + │                          │ (unmodified)      │
│ encoder + IMU   │                          └──────────────────┘
└───────────────┘
```

**Critical constraint:** The fusion core is a **companion, not a replacement.** It must sit as a discrete add-on that talks to an existing motor controller over a standard interface.

- Prototype interface: **SPI** (simplest)
- Production target: **EtherCAT** (what Bota and others already use)

---

## 2. Signal Chain — What You're Fusing

| Signal | Source | Typical interface | Role |
|---|---|---|---|
| Strain-gauge torque | Torque sensor or DIY strain-gauge bridge | Analog → ADC (or digital smart-sensor breakout) | Primary torque; noisy; drifts with temperature |
| Phase current | Shunt / current sensor on motor phases | Analog → ADC | Torque estimate via motor Kt — cross-check and sensorless fallback |
| Encoder position/velocity | Incremental or absolute encoder | Quadrature / SPI / SSI | Velocity-dependent compensation (friction, back-EMF); state estimation |
| IMU (optional, phase 2) | 6-axis IMU on joint/link | SPI/I2C | Whole-body/dynamic load; not required for MVP |
| Temperature | Thermistor near strain gauge | ADC | Often the single biggest accuracy lever (gauge drift) |

**MVP scope:** strain gauge + phase current + encoder + temperature compensation.  
**Skip for v1:** IMU fusion — adds complexity without proving the latency/bandwidth claim.

---

## 3. Estimation Algorithm

Start simple, get end-to-end working, then improve accuracy. Do not over-engineer the estimator before the pipeline works.

### Stage 1 — Complementary filter (build first)

- Fuse strain-gauge torque (accurate but slow/noisy) with current-derived torque (fast but less accurate; sensitive to Kt and temperature)
- Frequency-domain weighted blend: trust current for high-frequency content; trust strain gauge for low-frequency / steady-state
- Hardware at high rate alone is enough to demonstrate latency/bandwidth vs. software fusion

### Stage 2 — Kalman filter (once Stage 1 works)

- **State:** torque, torque rate, possibly temperature offset
- **Process model:** constant-torque-rate or physics-informed joint model
- **Measurements:** strain gauge + current-derived torque as two noisy observations of the same state
- Real accuracy gain over complementary filtering; matrix predict/update is a natural FPGA parallelism win vs. sequential MCU execution

### Stage 3 — Temperature compensation

- Fit compensation curve (linear or piecewise-linear) from bench calibration
- Apply as correction before or inside the filter

### Fixed-point vs. floating-point

Use **fixed-point** in the FPGA fabric — much cheaper in area/power than floating point, adequate for this signal range, and a demonstrable edge vs. MCU floating-point software. Call this out explicitly in the benchmark writeup.

---

## 4. Implementation Plan

### Step 1 — Bench setup

- Source or build a simple strain-gauge torque test rig (small DC/BLDC + strain-gauged torque arm, or a load cell if no proper torque sensor yet). Borrowing time on a real lab actuator is better for ground truth.
- Get raw ADC readings for strain gauge, current shunt, and encoder into the Kria PL (PMOD or similar on the carrier).

### Step 2 — Software reference implementation

- Implement complementary + Kalman filters in **Python/NumPy** against logged sensor data (correctness reference + cheap parameter tuning).
- Implement the **same** algorithm in C on the Kria ARM cores (or a separate MCU board for cleaner MCU comparison) — this is the benchmark baseline.

### Step 3 — HDL implementation

- Keep arithmetic in a shared HLS core with separate wrappers:
  `hls/aws_f2/` for PCIe batch validation and `hls/kria/` for the later
  embedded target.
- AWS F2 uses `m_axi` batch buffers and `s_axilite` controls; it does not model
  physical ADC, encoder, or SPI pins.
- Complementary filter first as fixed-point HLS; verify vs. Python on the same logged data.
- Kalman block next once complementary path is end-to-end.

### Step 4 — Output interface

- SPI slave so fused torque can be read by a real motor controller (or a second board simulating one).
- Proves the companion-chip integration story, not just internal compute.

### Step 5 — Benchmarking

Run identical input streams through (a) FPGA fusion core and (b) MCU software baseline.

Measure:

- Update rate
- End-to-end latency
- RMS error vs. calibrated reference torque
- Power (Kria power monitoring + comparable MCU board measurement)

Document clearly — **this writeup is the pitch** to design partners and investors.

### Step 6 — Design partner integration

- Package SPI output + basic config API so a lab/startup can wire into a real joint without heavy hand-holding.
- Run on someone else's hardware — the real test of the “drop-in companion” story.

---

## 5. Tooling

| Tool | Use |
|---|---|
| **Vitis / Vivado** | Standard Kria flow; Vivado for integration + ADC/encoder blocks |
| **Vitis HLS** | Filter math (complementary + Kalman) |
| **AWS F2 Developer Kit / XRT** | Cloud `hw_emu`, hardware compilation, host/DMA validation |
| **PYNQ** | Early PL bring-up from Python (if available for board variant) |
| **Python / NumPy** | Offline reference model; post-hoc analysis of logged benchmarks |
| **Scope / logic analyzer** | Independent latency verification (more credible than internal timestamps alone) |

---

## 6. What “Done” Looks Like for This Phase

A short demo + writeup showing:

1. Fusion core on Kria ingesting real sensor signals from a test rig
2. Comparison table: FPGA vs. MCU software — update rate / latency / accuracy / power
3. At least one successful read of the output by an external controller over SPI
4. Clear statement: whether the **5–10×** bar was met — and if not, the actual number (still useful for continue/stop)

That package opens design-partner conversations and is the evidence base for whether to pursue an ASIC.
