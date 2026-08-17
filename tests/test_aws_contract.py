import csv

from ftfusion.cli import main


def test_aws_vector_export_has_host_required_columns(tmp_path) -> None:
    vectors = tmp_path / "vectors.csv"
    exit_code = main(
        [
            "--duration",
            "0.01",
            "--check",
            "--vectors",
            str(vectors),
        ]
    )
    assert exit_code == 0
    with vectors.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        assert {
            "strain_torque_nm",
            "phase_current_a",
            "encoder_position_rad",
            "temperature_c",
            "fixed_fused_nm",
        }.issubset(reader.fieldnames or ())
        rows = list(reader)
    assert len(rows) == 100
    assert all(row["fixed_fused_nm"] for row in rows)
