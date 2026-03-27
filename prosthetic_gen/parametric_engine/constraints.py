"""
Socket Design Constraints
===========================
Anatomical, mechanical, and fabrication constraints for prosthetic socket generation.
All dimensions in millimeters unless noted otherwise.
"""

from dataclasses import dataclass, field
from typing import Optional

from ..measurement_input.schema import LoadZone


@dataclass
class SocketConstraints:
    """Constraint parameters governing socket geometry.
    
    These defaults are based on transradial prosthetic socket design guidelines.
    All values can be overridden for specific clinical requirements.
    """

    # --- Wall Thickness ---
    min_wall_thickness: float = 3.0        # mm — absolute minimum for structural integrity
    nominal_wall_thickness: float = 4.0    # mm — default wall thickness
    reinforcement_thickness: float = 5.5   # mm — at load-bearing areas
    distal_cap_thickness: float = 5.0      # mm — thicker at stump tip

    # --- Socket Fit Parameters ---
    socket_gap: float = 1.5                # mm — gap between stump and inner socket wall
    liner_thickness: float = 3.0           # mm — silicone liner allowance
    total_interface_gap: float = 4.5       # mm — socket_gap + liner_thickness

    # --- Geometry Constraints ---
    draft_angle_deg: float = 2.0           # degrees — for mold release / donning ease
    min_fillet_radius: float = 2.0         # mm — no sharp internal edges
    proximal_flare_angle_deg: float = 5.0  # degrees — flare at proximal trim line
    proximal_flare_height: float = 15.0    # mm — length of the flare section

    # --- Trim Line ---
    trim_line_offset: float = 20.0         # mm — trim line height above elbow
    trim_line_smoothing: float = 3.0       # mm — fillet at trim line edge

    # --- Distal End ---
    distal_cap_type: str = "rounded"       # "rounded", "flat", or "open"
    distal_cap_radius_factor: float = 0.8  # fraction of distal cross-section radius for cap curvature

    # --- Fabrication ---
    min_printable_feature: float = 1.0     # mm — smallest feature for FDM/SLA
    target_face_count: int = 50000         # target mesh face count for export

    # --- Load Zone Reinforcement ---
    load_zone_extra_thickness: float = 1.5  # mm — additional thickness at load-sensitive zones
    load_zone_blend_radius: float = 10.0    # mm — blend region around reinforcement

    # --- Phase 2: Forearm ---
    forearm_length: float = 250.0           # mm — default if contralateral not available
    forearm_wall_thickness: float = 3.0     # mm
    forearm_distal_diameter: float = 50.0   # mm — wrist-end diameter
    forearm_flange_thickness: float = 4.0   # mm — mounting flange at socket interface
    forearm_flange_width: float = 8.0       # mm — flange overhang

    # --- Phase 2: Wrist Joint ---
    wrist_joint_diameter: float = 40.0      # mm — male/female connector
    wrist_joint_length: float = 15.0        # mm — connector depth
    wrist_joint_clearance: float = 0.3      # mm — fit tolerance

    # --- Phase 2: Hand ---
    palm_width: float = 85.0               # mm
    palm_length: float = 100.0             # mm — wrist to knuckle line
    palm_thickness: float = 30.0           # mm
    palm_fillet_radius: float = 5.0        # mm — edge rounding

    # Finger parameters (proportional to palm_length)
    finger_base_diameter: float = 14.0     # mm — finger cross-section at knuckle
    finger_tip_diameter: float = 10.0      # mm — fingertip diameter
    finger_segment_ratios: tuple = (0.45, 0.30, 0.25)  # proximal, intermediate, distal
    finger_spacing: float = 18.0           # mm — center-to-center at knuckles
    finger_web_depth: float = 8.0          # mm — webbing between fingers

    # Finger lengths relative to middle finger (anatomical ratios)
    finger_length_ratios: tuple = (0.85, 1.0, 0.95, 0.80)  # index, middle, ring, pinky
    middle_finger_length: float = 80.0     # mm — absolute length of middle finger
    thumb_length: float = 55.0             # mm
    thumb_angle_deg: float = 45.0          # degrees — abduction angle from palm plane
    grip_angle_deg: float = 15.0           # degrees — default relaxed curl (0=flat, 90=fist)

    def get_outer_offset(self, station_pct: int, load_zones: int = 0) -> float:
        """Calculate total radial offset from stump surface to outer socket wall.
        
        Args:
            station_pct: Station percentage (0=proximal, 100=distal)
            load_zones: Bitwise LoadZone flags
            
        Returns:
            Total offset in mm (gap + liner + wall)
        """
        wall = self.nominal_wall_thickness

        # Thicker at distal end
        if station_pct >= 90:
            wall = self.distal_cap_thickness

        # Reinforcement at load zones
        if station_pct <= 25 and (load_zones & LoadZone.OLECRANON.value):
            wall = self.reinforcement_thickness
        if station_pct <= 25 and (load_zones & LoadZone.MEDIAL_EPICONDYLE.value):
            wall = self.reinforcement_thickness
        if station_pct <= 25 and (load_zones & LoadZone.LATERAL_EPICONDYLE.value):
            wall = self.reinforcement_thickness

        return self.total_interface_gap + wall

    def get_inner_offset(self) -> float:
        """Offset from stump surface to inner socket wall (gap + liner)."""
        return self.total_interface_gap

    def validate(self) -> list[str]:
        """Check constraint consistency. Returns list of issues."""
        issues = []
        if self.min_wall_thickness > self.nominal_wall_thickness:
            issues.append("min_wall_thickness exceeds nominal_wall_thickness")
        if self.nominal_wall_thickness > self.reinforcement_thickness:
            issues.append("nominal_wall_thickness exceeds reinforcement_thickness")
        if self.draft_angle_deg < 0 or self.draft_angle_deg > 15:
            issues.append(f"draft_angle_deg={self.draft_angle_deg} out of reasonable range [0, 15]")
        if self.total_interface_gap != (self.socket_gap + self.liner_thickness):
            issues.append("total_interface_gap should equal socket_gap + liner_thickness")
        return issues
