# Torque/Force Sensor Fusion Coprocessor — Project Summary

A dedicated real-time coprocessor that does torque/force estimation and multi-sensor fusion (strain, current, encoder, IMU) at control-loop speed, sold as a companion chip to existing motor controllers — not a replacement for them.

**Related docs**

- [`TECHNICAL_BRIEF.md`](TECHNICAL_BRIEF.md) — full FPGA prototype build plan (architecture, signals, algorithms, steps, done criteria)

---

## 1. Physics Foundation

### Force vs. torque

| Quantity | Meaning | Unit | Role in robotics |
|---|---|---|---|
| **Force** | Push or pull (linear) | Newtons (N) | Linear load at a point |
| **Torque** | Moment of a force about an axis (rotational) | Newton-meters (N·m) | What joints actually experience |

A **6-axis force/torque (F/T) sensor** measures force along X/Y/Z *and* torque about X/Y/Z simultaneously — the full load state at a wrist, ankle, or other mounting point.

### How F/T sensors work

Core principle: **apply a known load → measure tiny deformation → infer the load.**

| Sensing method | How it works | Pros | Cons / niche |
|---|---|---|---|
| **Strain gauges** (~80%+ of market) | Foil/semiconductor bonded to structure; resistance changes with strain; Wheatstone bridge → voltage | Mature, accurate | Drift, adhesive aging; mechanical “spider” design is hard IP |
| **Hall-effect** (e.g. PaXini) | Magnet displaces relative to Hall sensor as structure flexes | Less drift/aging; cheaper at volume | Newer approach |
| **Piezoelectric** | Crystal generates charge under force | Very stiff, fast | Poor static (DC) hold — charge leaks; machining/impact more than robot joints |
| **Capacitive / optical** | Gap change or light-path / FBG deflection | High precision, EMI immunity | Higher cost; medical/MRI-adjacent niches |

### Physical stack of a typical 6-axis sensor

1. **Mechanical structure** — Precision-machined body (Al, stainless, sometimes Ti) shaped so loads produce separable, predictable strain at gauge locations.
2. **Sensing elements** — Strain gauges (or Hall + magnets) in bridge circuits.
3. **Electronics** — AFE (instrumentation amps), ADC, MCU/DSP running calibration matrices → Fx/Fy/Fz/Tx/Ty/Tz, temp compensation, interface (EtherCAT, CAN, SPI).

**The opportunity lives in layer 3** — especially fusion/estimation compute — not in competing on strain-gauge mechanics or packaging.

### Where F/T sensing is used

- **Robotics** — wrists (assembly/insertion), humanoid ankles/hips/wrists, grippers, surgical haptics
- **Industrial** — CNC cutting force, screw-driving / press-fit verification, cobot contact safety
- **Automotive** — steering torque, pedal force, engine test benches
- **Aerospace** — landing gear loads, wind tunnel, actuator health
- **Medical** — prosthetics, rehab robotics, surgical instrument feedback
- **Consumer / misc** — torque wrenches, load cells, force-feedback controllers

---

## 2. Why a Chip (Not Another Sensor)

Raw strain/Hall signals are noisy and drifting. Clean torque usable inside a 1–10 kHz motor control loop needs:

- Filtering and temperature compensation
- Calibration / 6-axis decoupling matrices
- Cross-checks vs. motor current, encoder, IMU (fault detection + better accuracy)
- Deterministic, low-latency execution

### Bad status quo

| Approach | Problem |
|---|---|
| Fusion on the **same MCU** as FOC (C2000, STM32) | Competes with safety-critical control; fusion runs slower than mechanics allow |
| Fusion **inside the smart sensor** (Bota, PaXini, ATI, …) | Black box; fixed rate/filters; not tunable per application (grasping vs. rigid positioning vs. impact) |

### Product wedge

An **FPGA (then ASIC) companion coprocessor** that:

- Runs estimation at hardware speed (parallel, deterministic)
- Stays **separate** from the FOC safety path (no full system requalification)
- Is **programmable / SDK-tunable** per application and mechanics
- Does **not** fight the mechanical/materials moat of sensor vendors

---

## 3. Product Definition

### What it does

Sits alongside the main motor-control MCU and:

1. Ingests strain gauge / Hall torque signals, phase current, encoder position, optional IMU
2. Runs hardware-accelerated estimation (Kalman / complementary filtering, current+position cross-checks, temp compensation) above shared-MCU rates
3. Outputs clean, low-latency F/T estimates over a simple interface (SPI, EtherCAT-ready)
4. Ships with an SDK so customers tune estimators for their mechanics

### Roadmap fit (entry → endgame)

1. **Fusion coprocessor** (this product) — additive, lowest requalification risk  
2. **Multi-axis sync coprocessor**  
3. **Fused learned-model / control-loop SoC**

---

## 4. Technical Validation Plan

Full detail: [`TECHNICAL_BRIEF.md`](TECHNICAL_BRIEF.md).

### Phase goal

FPGA prototype on **Kria KV260 / KR260** that proves hardware-accelerated F/T estimation at higher update rate and lower latency than shared-MCU software fusion, at comparable or lower power. Not production-hardened — this validates or kills the ASIC case.

### Benchmark targets (set before coding)

| Metric | Example target |
|---|---|
| Update rate | 10 kHz+ fused output (vs. ~1–2 kHz typical on shared MCU) |
| End-to-end latency | <50 µs raw → fused |
| Accuracy | RMS error vs. calibrated reference torque |
| Power | Fusion logic isolated from rest of SoC |

**Go / no-go:** **5–10×** latency or update-rate improvement at equal/lower power. Miss → ASIC case not proven.

### Architecture (companion, not replacement)

Kria **PS (ARM)** for config/telemetry/SDK ↔ **PL (FPGA)** for:

1. **Sensor ingest** — ADC, encoder decode, (later) IMU SPI/I2C  
2. **Fusion core** — fixed-point complementary → Kalman; current cross-check; temp compensation  
3. **Output** — SPI slave to host FOC MCU (EtherCAT later)

### MVP signal set

Strain gauge + phase current + encoder + temperature. **Skip IMU for v1.**

### Estimator stages

1. Complementary filter (prove latency/bandwidth first)  
2. Kalman (torque / torque-rate / optional temp offset)  
3. Temp compensation curve from bench calibration  

Use **fixed-point** in fabric (area/power win vs. MCU float).

### Build sequence

1. Bench / test rig → raw ADC into PL  
2. Python/NumPy reference + C MCU baseline  
3. HLS/RTL: ingest → complementary → Kalman  
4. SPI slave to external controller  
5. Head-to-head FPGA vs. MCU benchmarks (scope-verified latency)  
6. Design-partner drop-in on someone else’s joint  

### Phase “done”

Demo + writeup: real signals on Kria; FPGA vs. MCU table (rate / latency / accuracy / power); SPI read by external controller; explicit 5–10× result (or the actual number if short).

---

## 5. Market Opportunity (Directional)

| Market | ~2026 size | Growth | Note |
|---|---|---|---|
| Torque sensors for robotic systems | ~$2.70B | ~11% CAGR to 2035 | Core addressable category |
| 6-axis F/T sensors | ~$1.02–1.2B | ~17.7% CAGR | ~45% share of torque-sensor category |
| Sensor fusion (all markets) | ~$16.7B | ~40% CAGR to 2035 | Auto-heavy today; robotics growing |
| Robotic sensors overall | ~$0.83B | ~8.4% CAGR | F/T ~31% of this |

**Caveat:** Headline numbers mostly count **complete sensor products**, not standalone fusion silicon. Addressable slice = compute layer inside or beside someone else’s sensor + drive. Treat as “real, growing market” context, not literal TAM.

### Tailwinds

- Humanoids / dexterous manipulators → high DOF (e.g. ~70) → many fusion instances per robot
- CES 2026 / embodied-AI sensors (e.g. PaXini) expanding whole-body force perception
- OEM investment in better fusion (e.g. FANUC/NVIDIA Jetson Thor for cobot sensor fusion)

---

## 6. Competitive Landscape

### Direct-ish (sensor companies — not chip/IP companies)

- **Bota Systems** — 6-axis F/T + IMU/temp; humanoid/medical/cobot; early-stage
- **PaXini** — Hall-effect 6D F/T for embodied AI / joint force control
- **ATI, FUTEK, HBK, Kistler, Sensodrive, TE Connectivity** — established industrial F/T
- **Celera Motion** — F/T for surgical robotics OEMs

**Gap:** None sell fusion/estimation as a **standalone, programmable, customer-tunable coprocessor** for someone else’s sensor + motor controller stack.

### Indirect (status quo)

TI C2000, STM32, and similar MCUs where fusion is software afterthought on the FOC chip.

---

## 7. Customers

| Stage | Who | Why |
|---|---|---|
| **First** | Robotics startups, university labs, in-house actuator teams | Need iteration speed; no proprietary fusion silicon |
| **Later** | Actuator manufacturers; industrial servo/drive OEMs | Volume and stability, but long sales cycles, certs, incumbent lock-in |

---

## 8. Risks

- Standalone fusion silicon TAM ≪ headline “$2.7B torque sensor” market
- Sensor vendors could add programmable fusion before traction
- FPGA win ≠ ASIC economics (re-validate power/cost at tapeout)
- Safety-adjacent robotics may demand IEC 61508 / ISO 13849-adjacent expectations even for a companion chip

---

## 9. Suggested Next Steps

1. Build FPGA fusion pipeline on Kria; benchmark vs. C2000-class software fusion  
2. Land 2–3 design partners (startups/labs with real actuators) and get IP on a test rig  
3. Use measured data to clear (or fail) the 5–10× bar before tapeout / serious capital raise  
4. Keep framing as step one of the larger roadmap, not a standalone company thesis alone  

---

## 10. One-Line Positioning

> Companion fusion silicon between raw F/T sensing and the robot brain — programmable, control-loop-fast, and separate from the motor-control MCU.
