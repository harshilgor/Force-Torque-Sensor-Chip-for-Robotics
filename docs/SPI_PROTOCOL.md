# SPI Companion Protocol v1

This document freezes a software-testable wire contract before an SPI slave is
implemented in FPGA logic.

## Transport assumptions

- Byte order: big-endian
- Integrity: CRC-16/CCITT-FALSE over header + payload
- SPI mode and maximum clock: deferred until the host MCU is selected
- The host initiates every transaction
- Sequence numbers detect dropped/repeated frames
- Timestamps are 32-bit microseconds and wrap naturally

## Common frame

| Offset | Size | Field |
|---:|---:|---|
| 0 | 2 | Magic ASCII `FT` |
| 2 | 1 | Protocol version (`1`) |
| 3 | 1 | Message type |
| 4 | 2 | Payload length |
| 6 | 4 | Sequence number |
| 10 | N | Payload |
| 10+N | 2 | CRC-16 |

## Message type 1: fused output

Payload size: 22 bytes.

| Offset | Size | Type | Field |
|---:|---:|---|---|
| 0 | 4 | uint32 | Timestamp, µs |
| 4 | 4 | signed Q16.16 | Fused torque, N·m |
| 8 | 4 | signed Q16.16 | Corrected strain torque, N·m |
| 12 | 4 | signed Q16.16 | Current-derived torque, N·m |
| 16 | 4 | signed Q16.16 | Encoder position, rad |
| 20 | 2 | bit flags | Status |

Status bits:

| Bit | Meaning |
|---:|---|
| 0 | Valid |
| 1 | Input invalid |
| 2 | Fixed-point saturation occurred |
| 3 | Calibration not loaded |
| 4 | Output stale |

## Message type 2: configuration write

Payload is seven signed Q16.16 fields:

1. Sample rate, Hz
2. Complementary crossover, Hz
3. Motor torque constant, N·m/A
4. Current offset, A
5. Strain offset, N·m
6. Strain temperature coefficient, N·m/°C
7. Reference temperature, °C

The eventual hardware protocol should add readback/acknowledgement and atomic
configuration activation. The current codec establishes encoding, validation,
versioning, corruption detection, and host-side tests.

Reference implementation: `src/ftfusion/protocol.py`.
