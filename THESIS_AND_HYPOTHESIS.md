# Thesis and Hypothesis

## Thesis

**The FPGA is not a step toward the ASIC. It is the evidence that decides whether you build the ASIC at all.**

Do not tape out until the fused-loop / hardware-acceleration advantage is proven. The Kria FPGA phase is that proof mechanism — not a prototype of the final product.

## Hypothesis

Hardware-accelerated multi-sensor torque/force fusion on dedicated fabric delivers a **5–10×** improvement in latency or update rate versus software fusion on a shared motor-control MCU, at equal or lower power.

This hypothesis is unproven until measured on real hardware. The FPGA phase exists to accept or reject it with a real number — not to assume it for a pitch.

---

## What the FPGA is actually doing

### 1. De-risk the algorithm before ASIC money

Tapeout is expensive and irreversible. Once an estimator design is committed to silicon, bugs or bad assumptions (wrong crossover frequency, wrong fixed-point format, an estimator that fails under real noise) cost a re-spin, not a recompile.

On the Kria, if the Q16.16 model fails once real strain-gauge noise hits it, that is an afternoon fix. The same mistake on silicon costs months and real money.

### 2. Benchmark the “5–10×” claim itself

Nobody yet knows whether hardware-accelerated fusion beats software fusion on a shared MCU by 5–10×, by 2×, or not at all. The FPGA is how that is measured honestly before building a business case or investor pitch around a guess.

If the FPGA only shows 2×, that changes whether the ASIC is worth pursuing. Better to learn that now.

### 3. Get design partners before chips exist

No robotics startup or lab will design around a chip that does not exist yet. They may integrate a Kria-based module into a test rig if it demonstrably improves torque estimation today.

That yields customer validation and field data (which feeds the ASIC’s spec) without asking anyone to bet on unproven silicon.

---

## What does *not* carry over 1:1 to the ASIC

- FPGA power numbers
- Exact resource usage
- Clock speeds

None of these predict ASIC power, area, or cost directly. FPGAs are inherently less efficient than custom silicon — that is why an ASIC is eventually attractive.

Hitting “FPGA power equal to or below shared-MCU baseline” is a useful signal, but it is **not** the same claim as “the ASIC will beat the MCU by X.” The ASIC’s real power/cost case is modeled separately later, using the FPGA’s **architecture and algorithm** as input — not its raw numbers.

---

## FPGA phase exit criteria

The FPGA phase ends with three outputs:

1. A validated, hardware-provable algorithm
2. An honest answer to whether the 5–10× claim is real
3. At least one design partner using it on real hardware

Only with those three in hand does “should we tape out an ASIC” become a decision with evidence behind it, rather than a bet.

---

## Related docs

- [`SUMMARY.md`](SUMMARY.md) — product thesis, market, competition
- [`TECHNICAL_BRIEF.md`](TECHNICAL_BRIEF.md) — Kria architecture, algorithms, build plan, success metrics
- [`docs/PHASE1_IMPLEMENTATION.md`](docs/PHASE1_IMPLEMENTATION.md) — Stage 1 status and frozen targets
