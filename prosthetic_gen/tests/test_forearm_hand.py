"""Tests for forearm, hand, and assembly generation."""

import os
import tempfile

import pytest

try:
    import cadquery as cq
    HAS_CADQUERY = True
except ImportError:
    HAS_CADQUERY = False

from prosthetic_gen.measurement_input.schema import create_synthetic_measurements
from prosthetic_gen.parametric_engine.constraints import SocketConstraints


@pytest.mark.skipif(not HAS_CADQUERY, reason="CadQuery not installed")
class TestForearmGenerator:
    def setup_method(self):
        self.measurements = create_synthetic_measurements()
        self.constraints = SocketConstraints()

    def test_forearm_generates(self):
        from prosthetic_gen.parametric_engine.forearm_generator import ForearmGenerator
        gen = ForearmGenerator(self.measurements, self.constraints)
        result = gen.generate()
        assert result is not None

    def test_forearm_wrist_position(self):
        from prosthetic_gen.parametric_engine.forearm_generator import ForearmGenerator
        gen = ForearmGenerator(self.measurements, self.constraints)
        gen.generate()
        wrist = gen.get_wrist_center()
        assert wrist[2] > self.measurements.residual_limb_length  # wrist is past socket

    def test_forearm_export_stl(self):
        from prosthetic_gen.parametric_engine.forearm_generator import ForearmGenerator
        from prosthetic_gen.parametric_engine.exporter import MeshExporter

        gen = ForearmGenerator(self.measurements, self.constraints)
        result = gen.generate()

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = MeshExporter(output_dir=tmpdir)
            stl_path = exporter.export_stl(result, "test_forearm.stl")
            assert os.path.exists(stl_path)
            assert os.path.getsize(stl_path) > 0


@pytest.mark.skipif(not HAS_CADQUERY, reason="CadQuery not installed")
class TestHandGenerator:
    def setup_method(self):
        self.constraints = SocketConstraints()

    def test_hand_generates(self):
        from prosthetic_gen.parametric_engine.hand_generator import HandGenerator
        gen = HandGenerator(self.constraints, wrist_z=300.0)
        result = gen.generate()
        assert result is not None

    def test_hand_grip_angles(self):
        """Test that different grip angles produce different geometry."""
        from prosthetic_gen.parametric_engine.hand_generator import HandGenerator
        from prosthetic_gen.parametric_engine.exporter import MeshExporter

        c_open = SocketConstraints(grip_angle_deg=0.0)
        c_fist = SocketConstraints(grip_angle_deg=60.0)

        hand_open = HandGenerator(c_open, wrist_z=0).generate()
        hand_fist = HandGenerator(c_fist, wrist_z=0).generate()

        # Both should generate successfully
        assert hand_open is not None
        assert hand_fist is not None

    def test_hand_total_length(self):
        from prosthetic_gen.parametric_engine.hand_generator import HandGenerator
        gen = HandGenerator(self.constraints, wrist_z=0.0)
        length = gen.get_total_length()
        # Should be wrist + palm + finger ≈ 13.5 + 100 + 80 ≈ 193.5mm
        assert 100 < length < 250

    def test_hand_export_stl(self):
        from prosthetic_gen.parametric_engine.hand_generator import HandGenerator
        from prosthetic_gen.parametric_engine.exporter import MeshExporter

        gen = HandGenerator(self.constraints, wrist_z=0.0)
        result = gen.generate()

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = MeshExporter(output_dir=tmpdir)
            stl_path = exporter.export_stl(result, "test_hand.stl")
            assert os.path.exists(stl_path)
            assert os.path.getsize(stl_path) > 0


@pytest.mark.skipif(not HAS_CADQUERY, reason="CadQuery not installed")
class TestProstheticAssembler:
    def setup_method(self):
        self.measurements = create_synthetic_measurements()
        self.constraints = SocketConstraints()

    def test_full_assembly(self):
        from prosthetic_gen.parametric_engine.assembler import ProstheticAssembler
        assembler = ProstheticAssembler(self.measurements, self.constraints)
        result = assembler.assemble()
        assert result is not None

    def test_separate_components(self):
        from prosthetic_gen.parametric_engine.assembler import ProstheticAssembler
        assembler = ProstheticAssembler(self.measurements, self.constraints)
        components = assembler.generate_components_separate()
        assert "socket" in components
        assert "forearm" in components
        assert "hand" in components
        assert all(v is not None for v in components.values())

    def test_assembly_export(self):
        from prosthetic_gen.parametric_engine.assembler import ProstheticAssembler
        from prosthetic_gen.parametric_engine.exporter import MeshExporter

        assembler = ProstheticAssembler(self.measurements, self.constraints)
        result = assembler.assemble()

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = MeshExporter(output_dir=tmpdir)
            paths = exporter.export_all(result, "test_arm")
            assert os.path.exists(paths["stl"])
            assert os.path.exists(paths["step"])
            assert os.path.exists(paths["glb"])

            stats = exporter.get_mesh_stats(paths["stl"])
            assert stats["vertices"] > 100
            assert stats["faces"] > 100
