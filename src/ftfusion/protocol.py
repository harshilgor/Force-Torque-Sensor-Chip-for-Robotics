"""Versioned SPI wire-format codec usable before physical hardware exists."""

import struct
from dataclasses import dataclass
from enum import IntEnum, IntFlag

from .complementary import FusionConfig
from .fixed_point import QFormat
from .models import FusionOutput

MAGIC = b"FT"
PROTOCOL_VERSION = 1
_HEADER = struct.Struct(">2sBBHI")
_OUTPUT_PAYLOAD = struct.Struct(">IiiiiH")
_CONFIG_PAYLOAD = struct.Struct(">iiiiiii")
_CRC = struct.Struct(">H")


class ProtocolError(ValueError):
    pass


class MessageType(IntEnum):
    FUSED_OUTPUT = 1
    CONFIG_WRITE = 2


class StatusFlag(IntFlag):
    VALID = 1 << 0
    INPUT_INVALID = 1 << 1
    SATURATED = 1 << 2
    UNCALIBRATED = 1 << 3
    STALE = 1 << 4


@dataclass(frozen=True, slots=True)
class OutputFrame:
    sequence: int
    timestamp_us: int
    torque_nm: float
    strain_corrected_nm: float
    current_torque_nm: float
    encoder_position_rad: float
    status: StatusFlag

    @classmethod
    def from_fusion_output(
        cls,
        output: FusionOutput,
        sequence: int,
        status: StatusFlag | None = None,
    ) -> "OutputFrame":
        resolved_status = status
        if resolved_status is None:
            resolved_status = (
                StatusFlag.VALID if output.valid else StatusFlag.INPUT_INVALID
            )
        return cls(
            sequence=sequence,
            timestamp_us=round(output.timestamp_s * 1_000_000.0),
            torque_nm=output.torque_nm,
            strain_corrected_nm=output.strain_corrected_nm,
            current_torque_nm=output.current_torque_nm,
            encoder_position_rad=output.encoder_position_rad,
            status=resolved_status,
        )


def crc16_ccitt(data: bytes, initial: int = 0xFFFF) -> int:
    """CRC-16/CCITT-FALSE: polynomial 0x1021, init 0xFFFF."""

    crc = initial
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else crc << 1
    return crc & 0xFFFF


def _encode_message(
    message_type: MessageType,
    sequence: int,
    payload: bytes,
) -> bytes:
    if not 0 <= sequence <= 0xFFFFFFFF:
        raise ProtocolError("sequence must fit uint32")
    header = _HEADER.pack(
        MAGIC,
        PROTOCOL_VERSION,
        int(message_type),
        len(payload),
        sequence,
    )
    body = header + payload
    return body + _CRC.pack(crc16_ccitt(body))


def _decode_message(
    encoded: bytes,
    expected_type: MessageType,
) -> tuple[int, bytes]:
    minimum_length = _HEADER.size + _CRC.size
    if len(encoded) < minimum_length:
        raise ProtocolError("frame is shorter than the protocol header")
    magic, version, message_type, payload_length, sequence = _HEADER.unpack_from(
        encoded
    )
    if magic != MAGIC:
        raise ProtocolError("invalid frame magic")
    if version != PROTOCOL_VERSION:
        raise ProtocolError(f"unsupported protocol version {version}")
    if message_type != int(expected_type):
        raise ProtocolError(f"unexpected message type {message_type}")
    expected_length = _HEADER.size + payload_length + _CRC.size
    if len(encoded) != expected_length:
        raise ProtocolError("frame length does not match payload length")
    expected_crc = _CRC.unpack_from(encoded, len(encoded) - _CRC.size)[0]
    actual_crc = crc16_ccitt(encoded[:-_CRC.size])
    if actual_crc != expected_crc:
        raise ProtocolError("frame CRC mismatch")
    return sequence, encoded[_HEADER.size : -_CRC.size]


def encode_output_frame(
    frame: OutputFrame,
    q_format: QFormat | None = None,
) -> bytes:
    q = q_format or QFormat()
    if not 0 <= frame.timestamp_us <= 0xFFFFFFFF:
        raise ProtocolError("timestamp_us must fit uint32")
    payload = _OUTPUT_PAYLOAD.pack(
        frame.timestamp_us,
        q.encode(frame.torque_nm),
        q.encode(frame.strain_corrected_nm),
        q.encode(frame.current_torque_nm),
        q.encode(frame.encoder_position_rad),
        int(frame.status),
    )
    return _encode_message(MessageType.FUSED_OUTPUT, frame.sequence, payload)


def decode_output_frame(
    encoded: bytes,
    q_format: QFormat | None = None,
) -> OutputFrame:
    q = q_format or QFormat()
    sequence, payload = _decode_message(encoded, MessageType.FUSED_OUTPUT)
    if len(payload) != _OUTPUT_PAYLOAD.size:
        raise ProtocolError("invalid fused-output payload length")
    timestamp, torque, strain, current, encoder, status = _OUTPUT_PAYLOAD.unpack(
        payload
    )
    return OutputFrame(
        sequence=sequence,
        timestamp_us=timestamp,
        torque_nm=q.decode(torque),
        strain_corrected_nm=q.decode(strain),
        current_torque_nm=q.decode(current),
        encoder_position_rad=q.decode(encoder),
        status=StatusFlag(status),
    )


def encode_config_frame(
    config: FusionConfig,
    sequence: int,
    q_format: QFormat | None = None,
) -> bytes:
    q = q_format or QFormat()
    payload = _CONFIG_PAYLOAD.pack(
        q.encode(config.sample_rate_hz),
        q.encode(config.crossover_hz),
        q.encode(config.motor_torque_constant_nm_per_a),
        q.encode(config.current_offset_a),
        q.encode(config.strain_offset_nm),
        q.encode(config.strain_temperature_coefficient_nm_per_c),
        q.encode(config.reference_temperature_c),
    )
    return _encode_message(MessageType.CONFIG_WRITE, sequence, payload)


def decode_config_frame(
    encoded: bytes,
    q_format: QFormat | None = None,
) -> tuple[int, FusionConfig]:
    q = q_format or QFormat()
    sequence, payload = _decode_message(encoded, MessageType.CONFIG_WRITE)
    if len(payload) != _CONFIG_PAYLOAD.size:
        raise ProtocolError("invalid config payload length")
    values = [q.decode(value) for value in _CONFIG_PAYLOAD.unpack(payload)]
    return sequence, FusionConfig(
        sample_rate_hz=values[0],
        crossover_hz=values[1],
        motor_torque_constant_nm_per_a=values[2],
        current_offset_a=values[3],
        strain_offset_nm=values[4],
        strain_temperature_coefficient_nm_per_c=values[5],
        reference_temperature_c=values[6],
    )
