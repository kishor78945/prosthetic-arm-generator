"""
End-to-end test for socket generation.
Requires CadQuery to be installed.
"""

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
from prosthetic_gen.parametric_engine.profile_generator import ProfileGenerator


@pytest.mark.skipif(not HAS_CADQUERY, reason="CadQuery not installed")
class TestSocketGeneration:
    def setup_method(self):
        self.measurements = create_synthetic_measurements()
        self.constraints = SocketConstraints()

    def test_profile_generation(self):
        gen = ProfileGenerator(self.measurements, self.constraints)
        profiles = gen.generate_all_outer_profiles()
        assert len(profiles) == 5
        for station, points in profiles.items():
            assert len(points) == 72
            for x, y in points:
                assert isinstance(x, float)
                assert isinstance(y, float)

    def test_inner_profiles_smaller_than_outer(self):
        gen = ProfileGenerator(self.measurements, self.constraints)
        for s in [0, 25, 50, 75, 100]:
            outer_a, outer_b = gen.get_outer_radii_at_station(s)
            inner_a, inner_b = gen.get_inner_radii_at_station(s)
            assert outer_a > inner_a
            assert outer_b > inner_b

    def test_socket_generation_simple(self):
        from prosthetic_gen.parametric_engine.socket_generator import SocketGenerator
        gen = SocketGenerator(self.measurements, self.constraints)
        result = gen.generate_simple()
        assert result is not None

    def test_socket_export_stl(self):
        from prosthetic_gen.parametric_engine.socket_generator import SocketGenerator
        from prosthetic_gen.parametric_engine.exporter import MeshExporter

        gen = SocketGenerator(self.measurements, self.constraints)
        result = gen.generate_simple()

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = MeshExporter(output_dir=tmpdir)
            stl_path = exporter.export_stl(result, "test_socket.stl")
            assert os.path.exists(stl_path)
            assert os.path.getsize(stl_path) > 0

            stats = exporter.get_mesh_stats(stl_path)
            assert stats["vertices"] > 0
            assert stats["faces"] > 0

    def test_socket_export_step(self):
        from prosthetic_gen.parametric_engine.socket_generator import SocketGenerator
        from prosthetic_gen.parametric_engine.exporter import MeshExporter

        gen = SocketGenerator(self.measurements, self.constraints)
        result = gen.generate_simple()

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = MeshExporter(output_dir=tmpdir)
            step_path = exporter.export_step(result, "test_socket.step")
            assert os.path.exists(step_path)
            assert os.path.getsize(step_path) > 0


@pytest.mark.skipif(not HAS_CADQUERY, reason="CadQuery not installed")
class TestDeterministicReplay:
    """Verify that identical inputs produce identical outputs."""

    def test_replay_produces_identical_hash(self):
        from prosthetic_gen.parametric_engine.socket_generator import SocketGenerator
        from prosthetic_gen.parametric_engine.exporter import MeshExporter
        from prosthetic_gen.postprocessing.validator import SocketValidator

        measurements = create_synthetic_measurements()
        constraints = SocketConstraints()

        hashes = []
        for _ in range(2):
            gen = SocketGenerator(measurements, constraints)
            result = gen.generate_simple()

            with tempfile.TemporaryDirectory() as tmpdir:
                exporter = MeshExporter(output_dir=tmpdir)
                stl_path = exporter.export_stl(result, "replay_test.stl")
                h = SocketValidator.compute_replay_hash(stl_path)
                hashes.append(h)

        assert hashes[0] == hashes[1], "Same inputs should produce identical outputs"
