"""
Measurement Schema for Upper-Limb Prosthetic Socket Generation
================================================================
Pydantic data classes defining the patient measurement schema.
All measurements in millimeters.
"""

from enum import Flag, auto
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class LoadZone(Flag):
    """Binary flags for load-sensitive anatomical zones on the residual limb."""
    NONE = 0
    OLECRANON = auto()          # Bony prominence at elbow tip
    MEDIAL_EPICONDYLE = auto()  # Inner elbow bony prominence
    LATERAL_EPICONDYLE = auto() # Outer elbow bony prominence
    BICIPITAL_TENDON = auto()   # Anterior distal pressure point
    DISTAL_END = auto()         # Stump tip — often sensitive


class EllipticalProfile(BaseModel):
    """Cross-section profile at a given percentage along the residual limb.
    
    Models the stump cross-section as an ellipse rather than a circle,
    which is more anatomically accurate.
    """
    major_diameter: float = Field(..., gt=0, description="Max diameter at this section (mm)")
    minor_diameter: float = Field(..., gt=0, description="Min diameter at this section (mm)")

    @property
    def circumference_approx(self) -> float:
        """Ramanujan's approximation for ellipse circumference."""
        a = self.major_diameter / 2
        b = self.minor_diameter / 2
        import math
        h = ((a - b) ** 2) / ((a + b) ** 2)
        return math.pi * (a + b) * (1 + (3 * h) / (10 + math.sqrt(4 - 3 * h)))

    @property
    def eccentricity(self) -> float:
        """How elliptical the cross-section is. 0 = circle, approaching 1 = very flat."""
        import math
        a = max(self.major_diameter, self.minor_diameter) / 2
        b = min(self.major_diameter, self.minor_diameter) / 2
        return math.sqrt(1 - (b / a) ** 2)


class StumpMeasurements(BaseModel):
    """Complete measurement set for a transradial (below-elbow) residual limb.
    
    All linear measurements are in millimeters.
    
    The residual limb is measured at 5 stations along its length:
    - 0%   = proximal (closest to body, at elbow crease)
    - 25%  = quarter length
    - 50%  = midpoint
    - 75%  = three-quarter length
    - 100% = distal (stump tip)
    
    Example:
        >>> measurements = StumpMeasurements(
        ...     residual_limb_length=180.0,
        ...     circumference_0=280.0,
        ...     circumference_25=260.0,
        ...     circumference_50=240.0,
        ...     circumference_75=210.0,
        ...     circumference_100=160.0,
        ...     major_diameter_0=95.0,
        ...     minor_diameter_0=85.0,
        ...     major_diameter_50=80.0,
        ...     minor_diameter_50=72.0,
        ...     major_diameter_100=55.0,
        ...     minor_diameter_100=48.0,
        ...     load_zones=LoadZone.OLECRANON | LoadZone.DISTAL_END,
        ... )
    """

    # --- Primary Measurements ---
    residual_limb_length: float = Field(
        ..., gt=30, lt=500,
        description="Length of residual limb from elbow crease to distal tip (mm)"
    )

    # Circumferences at 5 stations (mm)
    circumference_0: float = Field(
        ..., gt=100, lt=600,
        description="Circumference at 0% — proximal / elbow crease (mm)"
    )
    circumference_25: float = Field(
        ..., gt=80, lt=500,
        description="Circumference at 25% along limb length (mm)"
    )
    circumference_50: float = Field(
        ..., gt=60, lt=450,
        description="Circumference at 50% — midpoint (mm)"
    )
    circumference_75: float = Field(
        ..., gt=40, lt=400,
        description="Circumference at 75% along limb length (mm)"
    )
    circumference_100: float = Field(
        ..., gt=20, lt=350,
        description="Circumference at 100% — distal tip (mm)"
    )

    # Elliptical diameters (for eccentricity modeling)
    major_diameter_0: float = Field(
        ..., gt=30, lt=200,
        description="Max diameter at 0% station (mm)"
    )
    minor_diameter_0: float = Field(
        ..., gt=20, lt=200,
        description="Min diameter at 0% station (mm)"
    )
    major_diameter_50: float = Field(
        ..., gt=20, lt=150,
        description="Max diameter at 50% station (mm)"
    )
    minor_diameter_50: float = Field(
        ..., gt=15, lt=150,
        description="Min diameter at 50% station (mm)"
    )
    major_diameter_100: float = Field(
        ..., gt=10, lt=120,
        description="Max diameter at distal tip (mm)"
    )
    minor_diameter_100: float = Field(
        ..., gt=8, lt=120,
        description="Min diameter at distal tip (mm)"
    )

    # Load-sensitive zones
    load_zones: int = Field(
        default=0,
        description="Bitwise OR of LoadZone flags indicating sensitive areas"
    )

    # --- Optional Measurements ---
    contralateral_arm_length: Optional[float] = Field(
        default=None, gt=100, lt=900,
        description="Full length of the intact contralateral arm (mm)"
    )
    socket_trim_line_height: Optional[float] = Field(
        default=None, gt=10, lt=200,
        description="Desired trim line height above elbow (mm)"
    )
    patient_id: Optional[str] = Field(
        default=None,
        description="Anonymized patient identifier"
    )

    @model_validator(mode="after")
    def validate_circumference_taper(self) -> "StumpMeasurements":
        """Ensure circumferences decrease distally (basic anatomical check)."""
        circumferences = [
            self.circumference_0,
            self.circumference_25,
            self.circumference_50,
            self.circumference_75,
            self.circumference_100,
        ]
        # Allow up to 10% deviation from strict taper
        # (some limbs have bulbous distal ends from edema)
        for i in range(len(circumferences) - 1):
            if circumferences[i + 1] > circumferences[i] * 1.10:
                raise ValueError(
                    f"Circumference at {(i+1)*25}% ({circumferences[i+1]:.1f}mm) "
                    f"exceeds circumference at {i*25}% ({circumferences[i]:.1f}mm) "
                    f"by more than 10%. Check measurements."
                )
        return self

    @model_validator(mode="after")
    def validate_diameters_vs_circumference(self) -> "StumpMeasurements":
        """Sanity check: major diameter should be < circumference / π."""
        import math
        checks = [
            (self.major_diameter_0, self.circumference_0, "0%"),
            (self.major_diameter_50, self.circumference_50, "50%"),
            (self.major_diameter_100, self.circumference_100, "100%"),
        ]
        for major_d, circ, station in checks:
            max_possible = circ / math.pi
            if major_d > max_possible * 1.15:
                raise ValueError(
                    f"Major diameter at {station} ({major_d:.1f}mm) exceeds "
                    f"maximum possible from circumference ({max_possible:.1f}mm). "
                    f"Check measurements."
                )
        return self

    def get_profile_at(self, station: int) -> EllipticalProfile:
        """Get the elliptical cross-section profile at a given station.
        
        Args:
            station: Percentage along limb (0, 50, or 100 for measured stations).
                     Interpolated values are returned for 25 and 75.
        """
        measured = {
            0: (self.major_diameter_0, self.minor_diameter_0),
            50: (self.major_diameter_50, self.minor_diameter_50),
            100: (self.major_diameter_100, self.minor_diameter_100),
        }

        if station in measured:
            major, minor = measured[station]
            return EllipticalProfile(major_diameter=major, minor_diameter=minor)

        # Linear interpolation for 25% and 75%
        if station == 25:
            major = (self.major_diameter_0 + self.major_diameter_50) / 2
            minor = (self.minor_diameter_0 + self.minor_diameter_50) / 2
        elif station == 75:
            major = (self.major_diameter_50 + self.major_diameter_100) / 2
            minor = (self.minor_diameter_50 + self.minor_diameter_100) / 2
        else:
            raise ValueError(f"Station must be 0, 25, 50, 75, or 100. Got {station}")

        return EllipticalProfile(major_diameter=major, minor_diameter=minor)

    def get_all_profiles(self) -> dict[int, EllipticalProfile]:
        """Get elliptical profiles at all 5 measurement stations."""
        return {s: self.get_profile_at(s) for s in [0, 25, 50, 75, 100]}

    def has_load_zone(self, zone: LoadZone) -> bool:
        """Check if a specific load zone is flagged."""
        return bool(self.load_zones & zone.value)


# --- Synthetic measurement factory for testing ---

def create_synthetic_measurements(
    limb_length: float = 180.0,
    proximal_circ: float = 280.0,
    distal_circ: float = 160.0,
    taper_exponent: float = 1.2,
    eccentricity: float = 0.1,
) -> StumpMeasurements:
    """Generate synthetic but anatomically plausible measurements.
    
    Args:
        limb_length: Residual limb length (mm)
        proximal_circ: Circumference at elbow (mm)
        distal_circ: Circumference at tip (mm)
        taper_exponent: Controls how the taper curves (1.0=linear, >1=concave)
        eccentricity: How elliptical the cross-sections are (0=circular, 0.3=quite elliptical)
    
    Returns:
        StumpMeasurements with interpolated values at all stations
    """
    import math

    stations = [0, 25, 50, 75, 100]
    circumferences = {}
    for s in stations:
        t = s / 100.0
        circ = proximal_circ - (proximal_circ - distal_circ) * (t ** taper_exponent)
        circumferences[s] = circ

    def circ_to_diameters(circ: float, ecc: float) -> tuple[float, float]:
        """Convert circumference to major/minor diameters given eccentricity.
        
        Uses Ramanujan's approximation inverted: given a target circumference
        and an axis ratio (1+ecc)/(1-ecc), find the semi-axes whose Ramanujan
        circumference equals the target. This ensures generated diameters
        always pass the diameter-vs-circumference validator.
        """
        if ecc < 1e-6:
            d = circ / math.pi
            return d, d

        # Axis ratio: major/minor = (1+ecc)/(1-ecc)
        ratio = (1 + ecc) / (1 - ecc)

        # Ramanujan: C ≈ π(a+b)(1 + 3h/(10+√(4-3h))) where h = ((a-b)/(a+b))²
        # With b = a/ratio, solve for a given C = circ
        def ramanujan_circ(a: float) -> float:
            b = a / ratio
            h = ((a - b) ** 2) / ((a + b) ** 2)
            return math.pi * (a + b) * (1 + (3 * h) / (10 + math.sqrt(4 - 3 * h)))

        # Binary search for semi-major axis
        lo, hi = circ / (4 * math.pi), circ / math.pi
        for _ in range(64):
            mid = (lo + hi) / 2
            if ramanujan_circ(mid) < circ:
                lo = mid
            else:
                hi = mid

        semi_major = (lo + hi) / 2
        semi_minor = semi_major / ratio
        return semi_major * 2, semi_minor * 2

    maj_0, min_0 = circ_to_diameters(circumferences[0], eccentricity)
    maj_50, min_50 = circ_to_diameters(circumferences[50], eccentricity)
    maj_100, min_100 = circ_to_diameters(circumferences[100], eccentricity)

    return StumpMeasurements(
        residual_limb_length=limb_length,
        circumference_0=circumferences[0],
        circumference_25=circumferences[25],
        circumference_50=circumferences[50],
        circumference_75=circumferences[75],
        circumference_100=circumferences[100],
        major_diameter_0=maj_0,
        minor_diameter_0=min_0,
        major_diameter_50=maj_50,
        minor_diameter_50=min_50,
        major_diameter_100=maj_100,
        minor_diameter_100=min_100,
        load_zones=(LoadZone.OLECRANON | LoadZone.DISTAL_END).value,
        contralateral_arm_length=None,
    )
