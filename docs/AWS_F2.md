# AWS EC2 F2 Vitis Target

## Purpose

The AWS target is a temporary validation vehicle for the shared Q16.16 fusion
core. It answers:

- Does the core pass cycle-accurate hardware emulation?
- Does it synthesize and close timing for the F2 platform?
- What LUT, FF, DSP, BRAM, and timing estimates does Vitis report?
- Does an XRT host replay produce the same output as the Python golden model?

It does **not** measure live sensor-to-controller latency, target-product power,
or real actuator accuracy.

## Current AWS limitation

AWS's current F2 Vitis documentation says that Vitis AFI generation is not
supported on F2. Therefore:

- `hw_emu` can execute the host + accelerator in simulation without a physical
  FPGA.
- `hw` can compile the accelerator and produce implementation reports.
- A custom Vitis-built AFI cannot currently be generated and loaded onto an F2
  instance through this flow.

Use the platform exported by AWS's setup script rather than hard-coding the
example platform name. The official examples use:

```bash
PLATFORM=$SHELL_EMU_VERSION
```

References:

- [AWS F2 Vitis quick start](https://awsdocs-fpga-f2.readthedocs-hosted.com/latest/vitis/README.html)
- [AWS FPGA repository (`f2` branch)](https://github.com/aws/aws-fpga/tree/f2)

## Source layout

```text
hls/
├── common/
│   └── ftfusion_core.hpp       # shared Q16.16 arithmetic/state machine
├── kria/
│   ├── complementary_filter.*  # embedded scalar wrapper, retained for later
│   └── run_hls.tcl
└── aws_f2/
    ├── kernel.cpp/.hpp         # batch m_axi + s_axilite Vitis kernel
    ├── host.cpp                # XRT PCIe/DMA host and golden comparison
    ├── Makefile                # v++ compile/link/emulation flow
    └── xrt.ini                 # XRT profiling and timeline traces
```

The AWS batch kernel resets filter state at the beginning of every invocation.
Samples within one batch are processed in order with a requested initiation
interval of one cycle.

## AWS environment

Use an AWS FPGA Developer AMI or another supported Linux environment with
Vitis. The official setup is:

```bash
git clone --branch f2 https://github.com/aws/aws-fpga.git
cd aws-fpga
source vitis_setup.sh
install_xrt                 # only when setup reports that XRT is absent
source /opt/xilinx/xrt/setup.sh
```

The AWS setup script downloads/selects the compatible F2 platform and exports
`SHELL_EMU_VERSION`. Do not substitute a generic Alveo platform.

## Build and run hardware emulation

Install the Python package and create the software vectors:

```bash
cd /path/to/Force-Torque-Sensor-Chip-for-Robotics
python3 -m pip install -e '.[dev]'
cd hls/aws_f2
```

Then:

```bash
make run TARGET=hw_emu PLATFORM="$SHELL_EMU_VERSION"
```

The Makefile:

1. Exports a short deterministic CSV vector set.
2. Compiles `ftfusion_batch` to an `.xo`.
3. Links the F2 `.xclbin`.
4. Builds the XRT host.
5. Generates `emconfig.json`.
6. Executes hardware emulation and checks every output against Q16.16 golden
   values with a 0.001 N·m default tolerance.

Hardware emulation is cycle-accurate but uses approximate memory/interconnect
models. Keep its batch timing separate from real-hardware timing claims.

## Hardware compilation

```bash
make build TARGET=hw PLATFORM="$SHELL_EMU_VERSION"
```

This can take hours. Preserve:

- `ftfusion_batch.xclbin.info`
- `ftfusion_batch.xclbin.link_summary`
- `ftfusion_batch.link.xclbin.link_summary`
- Vitis compile/link reports

Record achieved clock, worst slack, initiation interval, latency in cycles, and
LUT/FF/DSP/BRAM use. Do not describe an `hw` build as execution on an FPGA.

## Metrics emitted by the host

- Host-to-device DMA time
- Batch kernel time (dispatch + completion as observed by XRT)
- Device-to-host DMA time
- Batch samples per second
- Maximum difference from the Python fixed-point model
- Invalid-output count

These are cloud batch metrics. They are not the `<50 µs` raw-signal-to-fused-SPI
acceptance measurement from the embedded product brief.

## Deferred until physical embedded hardware

- ADC/encoder interfaces and clock-domain synchronization
- Continuous stream behavior across physical samples
- SPI electrical implementation and timing
- Scope-verified per-sample latency
- PL rail power and thermal measurements
- Real strain/current/temperature calibration
