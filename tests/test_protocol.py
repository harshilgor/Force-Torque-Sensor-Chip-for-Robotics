import pytest

from ftfusion import FusionConfig, FusionOutput
from ftfusion.protocol import (
    OutputFrame,
    ProtocolError,
    StatusFlag,
    crc16_ccitt,
    decode_config_frame,
    decode_output_frame,
    encode_config_frame,
    encode_output_frame,
)


def test_known_crc16_ccitt_check_value() -> None:
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_output_frame_round_trip() -> None:
    output = FusionOutput(
        timestamp_s=0.123456,
        torque_nm=1.25,
        strain_corrected_nm=1.2,
        current_torque_nm=1.3,
        encoder_position_rad=-0.75,
        valid=True,
    )
    frame = OutputFrame.from_fusion_output(output, sequence=42)
    decoded = decode_output_frame(encode_output_frame(frame))
    assert decoded.sequence == 42
    assert decoded.timestamp_us == 123456
    assert decoded.torque_nm == pytest.approx(1.25)
    assert decoded.encoder_position_rad == pytest.approx(-0.75)
    assert decoded.status == StatusFlag.VALID


def test_crc_detects_corrupted_output_frame() -> None:
    frame = OutputFrame(
        sequence=1,
        timestamp_us=10,
        torque_nm=0.5,
        strain_corrected_nm=0.5,
        current_torque_nm=0.5,
        encoder_position_rad=0.0,
        status=StatusFlag.VALID,
    )
    encoded = bytearray(encode_output_frame(frame))
    encoded[12] ^= 0x01
    with pytest.raises(ProtocolError, match="CRC"):
        decode_output_frame(bytes(encoded))


def test_config_frame_round_trip() -> None:
    config = FusionConfig(
        sample_rate_hz=10_000.0,
        crossover_hz=25.0,
        motor_torque_constant_nm_per_a=0.125,
        current_offset_a=-0.02,
        strain_offset_nm=0.04,
        strain_temperature_coefficient_nm_per_c=0.003,
        reference_temperature_c=26.0,
    )
    sequence, decoded = decode_config_frame(
        encode_config_frame(config, sequence=99)
    )
    assert sequence == 99
    assert decoded.sample_rate_hz == pytest.approx(
        config.sample_rate_hz, abs=1 / 65536
    )
    assert decoded.crossover_hz == pytest.approx(
        config.crossover_hz, abs=1 / 65536
    )
    assert decoded.motor_torque_constant_nm_per_a == pytest.approx(
        config.motor_torque_constant_nm_per_a,
        abs=1 / 65536,
    )
    assert decoded.current_offset_a == pytest.approx(
        config.current_offset_a, abs=1 / 65536
    )
