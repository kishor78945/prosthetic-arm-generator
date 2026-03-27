"""
Forearm Tube Generator
========================
CadQuery-based forearm tube connecting socket to wrist joint.
Anatomical elliptical cross-sections with ulnar ridge.
"""

import math
from typing import Optional

import cadquery as cq
import numpy as np

from ..measurement_input.schema import StumpMeasurements
from .constraints import SocketConstraints
from .profile_generator import ProfileGenerator


class ForearmGenerator:
    """Generates a hollow forearm tube with anatomical elliptical cross-sections.

    Improvements over simple circular taper:
    - Elliptical cross-sections (forearms are wider than deep, ratio ~1.25:1)
    - 5-station continuous loft for smooth organic taper
    - Subtle ulnar ridge on the medial side (bounded ≤3mm)
    - Mounting flanges at socket and wrist interfaces

    All dimensions are measurement-derived and deterministic.
    """

    # Anatomical ratio: forearm width / forearm depth
    ELLIPSE_RATIO = 1.25

    # Ulnar ridge: max amplitude in mm (bounded for reviewer safety)
    MAX_ULNAR_RIDGE_MM = 3.0

    def __init__(
        self,
        measurements: StumpMeasurements,
        constraints: Optional[SocketConstraints] = None,
    ):
        self.measurements = measurements
        self.constraints = constraints or SocketConstraints()
        self.profile_gen = ProfileGenerator(measurements, self.constraints)
        self._result: Optional[cq.Workplane] = None

    def _get_socket_distal_z(self) -> float:
        """Z position where socket ends (distal cap top)."""
        socket_length = self.measurements.residual_limb_length
        cap_thickness = self.constraints.distal_cap_thickness
        return socket_length + cap_thickness

    def _get_proximal_diameter(self) -> float:
        """Forearm proximal diameter — matches socket's distal outer diameter."""
        semi_a, semi_b = self.profile_gen.get_outer_radii_at_station(100)
        # Use average diameter for compatibility
        return (semi_a + semi_b)

    def _get_forearm_length(self) -> float:
        """Compute forearm length from contralateral arm or default."""
        if self.measurements.contralateral_arm_length:
            total = self.measurements.contralateral_arm_length
            remaining = total - self.measurements.residual_limb_length
            return max(remaining * 0.55, 100.0)
        return self.constraints.forearm_length

    def _ellipse_radii_at_t(self, t: float) -> tuple[float, float]:
        """Get elliptical semi-major/minor radii at position t (0=proximal, 1=distal).

        Uses anatomical ellipse ratio (width > depth) and a smooth
        taper profile instead of linear.
        """
        proximal_d = self._get_proximal_diameter()
        distal_d = self.constraints.forearm_distal_diameter

        proximal_r = proximal_d / 2
        distal_r = distal_d / 2

        # Smooth taper: slight S-curve (not strictly linear) for organic feel
        # Using smoothstep: 3t² - 2t³
        t_smooth = 3 * t * t - 2 * t * t * t
        avg_r = proximal_r + (distal_r - proximal_r) * t_smooth

        # Apply elliptical ratio
        semi_major = avg_r * math.sqrt(self.ELLIPSE_RATIO)     # width (X)
        semi_minor = avg_r / math.sqrt(self.ELLIPSE_RATIO)     # depth (Y)

        return semi_major, semi_minor

    def _ulnar_ridge_offset(self, t: float) -> float:
        """Ulnar ridge amplitude at position t.

        The ridge is most prominent at mid-forearm and tapers
        to zero at both ends. Bounded ≤ MAX_ULNAR_RIDGE_MM.

        Returns offset in mm (always ≥ 0).
        """
        # Bell curve: peak at t=0.4 (anatomically, ulnar prominence
        # is in the proximal third of the forearm)
        peak_t = 0.4
        sigma = 0.25
        amplitude = self.MAX_ULNAR_RIDGE_MM * math.exp(
            -0.5 * ((t - peak_t) / sigma) ** 2
        )
        return min(amplitude, self.MAX_ULNAR_RIDGE_MM)

    def generate(self) -> cq.Workplane:
        """Generate the forearm tube with anatomical elliptical cross-sections.

        Returns:
            CadQuery Workplane with the forearm tube solid.
        """
        c = self.constraints
        z_start = self._get_socket_distal_z()
        length = self._get_forearm_length()
        wall = c.forearm_wall_thickness

        # --- 1. Mounting flange at proximal end ---
        proximal_d = self._get_proximal_diameter()
        proximal_r = proximal_d / 2
        flange_r = proximal_r + c.forearm_flange_width
        flange = (
            cq.Workplane("XY")
            .workplane(offset=z_start)
            .circle(flange_r)
            .circle(proximal_r - wall)
            .extrude(c.forearm_flange_thickness)
        )

        # --- 2. Main tube body: 5-station elliptical loft ---
        tube_z_start = z_start + c.forearm_flange_thickness
        tube_length = length - c.forearm_flange_thickness - c.wrist_joint_length

        # 5 stations along tube body
        n_stations = 5
        stations_t = [i / (n_stations - 1) for i in range(n_stations)]

        # Build outer and inner section data
        outer_sections = []
        inner_sections = []
        for t in stations_t:
            z = tube_z_start + t * tube_length
            sa, sb = self._ellipse_radii_at_t(t)

            # Add ulnar ridge offset to medial (positive X) side
            # Implemented as asymmetric semi-major increase
            ridge = self._ulnar_ridge_offset(t)
            sa_outer = sa + ridge / 2  # distribute ridge symmetrically for loft compat

            outer_sections.append((z, sa_outer, sb))
            inner_sections.append((z, sa_outer - wall, sb - wall))

        # Build outer solid as single continuous loft
        outer_wp = cq.Workplane("XY")
        for i, (z, sa, sb) in enumerate(outer_sections):
            if i == 0:
                outer_wp = outer_wp.workplane(offset=z).ellipse(sa, sb)
            else:
                dz = z - outer_sections[i - 1][0]
                outer_wp = outer_wp.workplane(offset=dz).ellipse(sa, sb)
        outer_solid = outer_wp.loft(combine=True)

        # Build inner solid
        inner_wp = cq.Workplane("XY")
        for i, (z, sa, sb) in enumerate(inner_sections):
            if i == 0:
                inner_wp = inner_wp.workplane(offset=z).ellipse(sa, sb)
            else:
                dz = z - inner_sections[i - 1][0]
                inner_wp = inner_wp.workplane(offset=dz).ellipse(sa, sb)
        inner_solid = inner_wp.loft(combine=True)

        tube = outer_solid.cut(inner_solid)

        # --- 3. Wrist connector (female socket) ---
        wrist_z = tube_z_start + tube_length
        wrist_outer_r = self.constraints.forearm_distal_diameter / 2
        wrist_inner_r = c.wrist_joint_diameter / 2
        wrist_length = c.wrist_joint_length

        wrist_connector = (
            cq.Workplane("XY")
            .workplane(offset=wrist_z)
            .circle(wrist_outer_r)
            .circle(wrist_inner_r + c.wrist_joint_clearance)
            .extrude(wrist_length)
        )

        # Combine all parts
        result = flange.union(tube).union(wrist_connector)

        # Apply fillets to transitions
        try:
            result = result.edges("|Z").fillet(1.5)
        except Exception:
            pass

        self._result = result
        return result

    @property
    def result(self) -> Optional[cq.Workplane]:
        return self._result

    def get_distal_z(self) -> float:
        """Z position at the end of the forearm (wrist connector end)."""
        z_start = self._get_socket_distal_z()
        length = self._get_forearm_length()
        return z_start + length

    def get_wrist_center(self) -> tuple[float, float, float]:
        """Center point of the wrist connector for hand attachment."""
        return (0.0, 0.0, self.get_distal_z())

