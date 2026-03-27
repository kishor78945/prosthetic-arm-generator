"""
Cross-Section Profile Generator
==================================
Generates B-spline elliptical cross-section profiles from patient measurements.
Profiles are used as wire inputs for CadQuery lofting operations.
"""

import math
from typing import Optional

import numpy as np

from ..measurement_input.schema import StumpMeasurements, EllipticalProfile
from .constraints import SocketConstraints


class ProfileGenerator:
    """Generates inner and outer cross-section profiles for the prosthetic socket.
    
    Given patient measurements and socket constraints, produces elliptical
    cross-sections at each measurement station. These profiles are then
    lofted together in the SocketGenerator to create the 3D socket geometry.
    """

    def __init__(
        self,
        measurements: StumpMeasurements,
        constraints: Optional[SocketConstraints] = None,
        num_profile_points: int = 72,
    ):
        """
        Args:
            measurements: Patient stump measurements
            constraints: Socket design constraints (defaults used if None)
            num_profile_points: Number of points per cross-section (higher = smoother)
        """
        self.measurements = measurements
        self.constraints = constraints or SocketConstraints()
        self.num_points = num_profile_points

    def _ellipse_points(
        self,
        semi_major: float,
        semi_minor: float,
        center_x: float = 0.0,
        center_y: float = 0.0,
        num_points: Optional[int] = None,
    ) -> list[tuple[float, float]]:
        """Generate points on an ellipse in the XY plane.
        
        Args:
            semi_major: Half of major axis (X direction)
            semi_minor: Half of minor axis (Y direction)
            center_x: Center X offset
            center_y: Center Y offset
            num_points: Override for number of points
            
        Returns:
            List of (x, y) tuples forming the ellipse
        """
        n = num_points or self.num_points
        points = []
        for i in range(n):
            theta = 2 * math.pi * i / n
            x = center_x + semi_major * math.cos(theta)
            y = center_y + semi_minor * math.sin(theta)
            points.append((x, y))
        return points

    def generate_stump_profile(
        self, station_pct: int
    ) -> list[tuple[float, float]]:
        """Generate the stump surface cross-section at a given station.
        
        Args:
            station_pct: Percentage along limb (0, 25, 50, 75, 100)
            
        Returns:
            List of (x, y) points representing the stump surface shape
        """
        profile = self.measurements.get_profile_at(station_pct)
        return self._ellipse_points(
            semi_major=profile.major_diameter / 2,
            semi_minor=profile.minor_diameter / 2,
        )

    def generate_inner_wall_profile(
        self, station_pct: int
    ) -> list[tuple[float, float]]:
        """Generate inner socket wall profile (stump + interface gap).
        
        The inner wall is offset outward from the stump surface by the
        total interface gap (socket gap + liner thickness).
        """
        profile = self.measurements.get_profile_at(station_pct)
        gap = self.constraints.get_inner_offset()
        return self._ellipse_points(
            semi_major=profile.major_diameter / 2 + gap,
            semi_minor=profile.minor_diameter / 2 + gap,
        )

    def generate_outer_wall_profile(
        self, station_pct: int
    ) -> list[tuple[float, float]]:
        """Generate outer socket wall profile (stump + gap + liner + wall).
        
        The outer wall includes the full offset: interface gap plus wall thickness.
        Thickness varies by station and load zone configuration.
        """
        profile = self.measurements.get_profile_at(station_pct)
        offset = self.constraints.get_outer_offset(
            station_pct, self.measurements.load_zones
        )
        return self._ellipse_points(
            semi_major=profile.major_diameter / 2 + offset,
            semi_minor=profile.minor_diameter / 2 + offset,
        )

    def generate_all_outer_profiles(
        self,
    ) -> dict[int, list[tuple[float, float]]]:
        """Generate outer wall profiles at all 5 measurement stations.

        Returns:
            Dict mapping station_pct → list of (x, y) points
        """
        return {s: self.generate_outer_wall_profile(s) for s in [0, 25, 50, 75, 100]}

    def generate_all_inner_profiles(
        self,
    ) -> dict[int, list[tuple[float, float]]]:
        """Generate inner wall profiles at all 5 measurement stations."""
        return {s: self.generate_inner_wall_profile(s) for s in [0, 25, 50, 75, 100]}

    def get_station_z(self, station_pct: int) -> float:
        """Get the Z-coordinate (height) for a given station.
        
        Z=0 is at the proximal end (0%), increasing distally.
        
        Args:
            station_pct: Percentage along limb
            
        Returns:
            Z-coordinate in mm
        """
        return self.measurements.residual_limb_length * station_pct / 100.0

    def get_profile_3d(
        self, station_pct: int, wall: str = "outer"
    ) -> list[tuple[float, float, float]]:
        """Get 3D profile points (x, y, z) at a station.
        
        Args:
            station_pct: Station percentage
            wall: "outer", "inner", or "stump"
            
        Returns:
            List of (x, y, z) tuples
        """
        if wall == "outer":
            xy = self.generate_outer_wall_profile(station_pct)
        elif wall == "inner":
            xy = self.generate_inner_wall_profile(station_pct)
        elif wall == "stump":
            xy = self.generate_stump_profile(station_pct)
        else:
            raise ValueError(f"wall must be 'outer', 'inner', or 'stump'. Got '{wall}'")

        z = self.get_station_z(station_pct)
        return [(x, y, z) for x, y in xy]

    def get_outer_radii_at_station(self, station_pct: int) -> tuple[float, float]:
        """Get the semi-major and semi-minor radii of the outer wall at a station.

        Returns:
            (semi_major, semi_minor) in mm
        """
        profile = self.measurements.get_profile_at(station_pct)
        offset = self.constraints.get_outer_offset(
            station_pct, self.measurements.load_zones
        )
        return (
            profile.major_diameter / 2 + offset,
            profile.minor_diameter / 2 + offset,
        )

    def get_inner_radii_at_station(self, station_pct: int) -> tuple[float, float]:
        """Get the semi-major and semi-minor radii of the inner wall at a station.

        Returns:
            (semi_major, semi_minor) in mm
        """
        profile = self.measurements.get_profile_at(station_pct)
        gap = self.constraints.get_inner_offset()
        return (
            profile.major_diameter / 2 + gap,
            profile.minor_diameter / 2 + gap,
        )
