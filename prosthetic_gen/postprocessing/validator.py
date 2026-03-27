"""
Socket Validator
==================
Dimensional validation of generated socket against input measurements.
Ensures clinical tolerances are met.
"""

import hashlib
import math
from pathlib import Path
from typing import Optional

import numpy as np
import trimesh

from ..measurement_input.schema import StumpMeasurements
from ..parametric_engine.constraints import SocketConstraints
from ..parametric_engine.profile_generator import ProfileGenerator


class ValidationResult:
    """Container for validation check results."""

    def __init__(self):
        self.checks: list[dict] = []
        self.passed: bool = True

    def add_check(
        self,
        name: str,
        expected: float,
        actual: float,
        tolerance: float,
        unit: str = "mm",
    ):
        deviation = abs(actual - expected)
        ok = deviation <= tolerance
        self.checks.append({
            "name": name,
            "expected": expected,
            "actual": actual,
            "deviation": deviation,
            "tolerance": tolerance,
            "unit": unit,
            "passed": ok,
        })
        if not ok:
            self.passed = False

    def add_boolean_check(self, name: str, value: bool, expected: bool = True):
        ok = value == expected
        self.checks.append({
            "name": name,
            "value": value,
            "expected": expected,
            "passed": ok,
        })
        if not ok:
            self.passed = False

    def summary(self) -> str:
        lines = []
        for c in self.checks:
            status = "✅" if c["passed"] else "❌"
            if "deviation" in c:
                lines.append(
                    f'{status} {c["name"]}: expected={c["expected"]:.2f}{c["unit"]}, '
                    f'actual={c["actual"]:.2f}{c["unit"]}, '
                    f'deviation={c["deviation"]:.2f}{c["unit"]} '
                    f'(tol={c["tolerance"]:.2f}{c["unit"]})'
                )
            else:
                lines.append(
                    f'{status} {c["name"]}: {c["value"]} (expected {c["expected"]})'
                )
        overall = "PASSED" if self.passed else "FAILED"
        lines.append(f"\nOverall: {overall}")
        return "\n".join(lines)


class SocketValidator:
    """Validates generated socket geometry against input measurements.
    
    Checks:
    - Cross-section circumference deviation at each station
    - Socket volume within expected range
    - Watertightness
    - Wall thickness at sampled points
    - Overall bounding box dimensions
    """

    def __init__(
        self,
        measurements: StumpMeasurements,
        constraints: Optional[SocketConstraints] = None,
        circumference_tolerance: float = 1.0,
        volume_tolerance_pct: float = 2.0,
        wall_thickness_tolerance: float = 0.5,
    ):
        """
        Args:
            measurements: Original input measurements
            constraints: Socket constraints used for generation
            circumference_tolerance: Max allowed deviation in mm
            volume_tolerance_pct: Max allowed volume deviation in %
            wall_thickness_tolerance: Tolerance on wall thickness in mm
        """
        self.measurements = measurements
        self.constraints = constraints or SocketConstraints()
        self.profile_gen = ProfileGenerator(measurements, self.constraints)
        self.circ_tol = circumference_tolerance
        self.vol_tol_pct = volume_tolerance_pct
        self.wall_tol = wall_thickness_tolerance

    def validate_mesh(self, mesh_path: str) -> ValidationResult:
        """Run all validation checks on an exported mesh.
        
        Args:
            mesh_path: Path to STL/GLB mesh file
            
        Returns:
            ValidationResult with all check outcomes
        """
        mesh = trimesh.load(mesh_path)
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(list(mesh.geometry.values()))

        result = ValidationResult()

        # 1. Watertightness
        result.add_boolean_check("Watertight", mesh.is_watertight, expected=True)

        # 2. Bounding box height ≈ residual limb length + cap
        expected_height = self.measurements.residual_limb_length
        if self.constraints.distal_cap_type != "open":
            expected_height += self.constraints.distal_cap_thickness
        actual_height = mesh.bounds[1][2] - mesh.bounds[0][2]
        result.add_check(
            "Socket height (Z-axis)",
            expected=expected_height,
            actual=actual_height,
            tolerance=2.0,  # 2mm tolerance on overall height
        )

        # 3. Cross-section checks at each station
        self._validate_cross_sections(mesh, result)

        # 4. Volume sanity check
        if mesh.is_watertight:
            self._validate_volume(mesh, result)

        # 5. Wall thickness spot checks
        self._validate_wall_thickness(mesh, result)

        return result

    def _validate_cross_sections(self, mesh: trimesh.Trimesh, result: ValidationResult):
        """Slice the mesh at each station and compare circumference."""
        stations = [0, 25, 50, 75, 100]

        for s in stations:
            z = self.profile_gen.get_station_z(s)

            try:
                # Slice the mesh at this Z height
                sliced = mesh.section(
                    plane_origin=[0, 0, z],
                    plane_normal=[0, 0, 1],
                )
                if sliced is None:
                    result.add_boolean_check(
                        f"Cross-section exists at {s}%", False, expected=True
                    )
                    continue

                # Get the 2D path and compute perimeter
                path_2d, _ = sliced.to_planar()
                actual_perimeter = sum(
                    entity.length(path_2d.vertices) for entity in path_2d.entities
                )

                # Expected outer circumference
                semi_a, semi_b = self.profile_gen.get_outer_radii_at_station(s)
                a, b = semi_a, semi_b
                h = ((a - b) ** 2) / ((a + b) ** 2)
                expected_circ = math.pi * (a + b) * (1 + (3 * h) / (10 + math.sqrt(4 - 3 * h)))

                result.add_check(
                    f"Outer circumference at {s}%",
                    expected=expected_circ,
                    actual=actual_perimeter,
                    tolerance=self.circ_tol,
                )
            except Exception as e:
                result.add_boolean_check(
                    f"Cross-section analysis at {s}%", False, expected=True
                )

    def _validate_volume(self, mesh: trimesh.Trimesh, result: ValidationResult):
        """Check that socket volume is within expected bounds."""
        # Estimate expected volume from profiles
        # Approximate as sum of truncated elliptical cone segments
        stations = [0, 25, 50, 75, 100]
        expected_volume = 0.0

        for i in range(len(stations) - 1):
            h = self.profile_gen.get_station_z(stations[i + 1]) - self.profile_gen.get_station_z(stations[i])
            a1_out, b1_out = self.profile_gen.get_outer_radii_at_station(stations[i])
            a2_out, b2_out = self.profile_gen.get_outer_radii_at_station(stations[i + 1])
            a1_in, b1_in = self.profile_gen.get_inner_radii_at_station(stations[i])
            a2_in, b2_in = self.profile_gen.get_inner_radii_at_station(stations[i + 1])

            vol_outer = (math.pi * h / 3) * (
                a1_out * b1_out + a2_out * b2_out + math.sqrt(a1_out * b1_out * a2_out * b2_out)
            )
            vol_inner = (math.pi * h / 3) * (
                a1_in * b1_in + a2_in * b2_in + math.sqrt(a1_in * b1_in * a2_in * b2_in)
            )
            expected_volume += vol_outer - vol_inner

        actual_volume = abs(mesh.volume)
        deviation_pct = abs(actual_volume - expected_volume) / expected_volume * 100

        result.add_check(
            "Socket wall volume",
            expected=expected_volume,
            actual=actual_volume,
            tolerance=expected_volume * self.vol_tol_pct / 100,
            unit="mm³",
        )

    def _validate_wall_thickness(self, mesh: trimesh.Trimesh, result: ValidationResult):
        """Spot-check wall thickness using ray casting.
        
        Casts rays inward from the outer surface and measures distances.
        """
        min_wall = self.constraints.min_wall_thickness

        # Sample points on the mesh surface
        try:
            points, face_indices = trimesh.sample.sample_surface(mesh, count=100)
            normals = mesh.face_normals[face_indices]

            # Cast rays inward
            ray_origins = points + normals * 0.01  # slightly outside
            ray_directions = -normals

            locations, index_ray, _ = mesh.ray.intersects_location(
                ray_origins=ray_origins,
                ray_directions=ray_directions,
            )

            if len(locations) > 0:
                # For each ray, find the distance to the nearest hit
                thicknesses = []
                for i in range(len(ray_origins)):
                    mask = index_ray == i
                    if mask.any():
                        hits = locations[mask]
                        dists = np.linalg.norm(hits - ray_origins[i], axis=1)
                        # Filter out self-hits
                        valid = dists > 0.1
                        if valid.any():
                            thicknesses.append(float(dists[valid].min()))

                if thicknesses:
                    min_measured = min(thicknesses)
                    result.add_check(
                        "Minimum wall thickness (sampled)",
                        expected=min_wall,
                        actual=min_measured,
                        tolerance=self.wall_tol,
                    )
                    return

            result.add_boolean_check("Wall thickness measurable", False, expected=True)
        except Exception:
            result.add_boolean_check("Wall thickness analysis", False, expected=True)

    @staticmethod
    def compute_replay_hash(mesh_path: str) -> str:
        """Compute SHA-256 hash of a mesh file for deterministic replay verification.
        
        Args:
            mesh_path: Path to the mesh file
            
        Returns:
            Hex digest of SHA-256 hash
        """
        h = hashlib.sha256()
        with open(mesh_path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
