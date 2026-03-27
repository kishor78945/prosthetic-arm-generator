"""
Measurement Normalizer
========================
Outlier detection, consistency checks, and normalization for patient measurements.
"""

import math
from typing import Optional

from .schema import StumpMeasurements, EllipticalProfile


# Population-level statistics for transradial residual limbs (adult)
# Source: Compiled from prosthetic literature (approximate ranges)
POPULATION_STATS = {
    "residual_limb_length": {"mean": 170.0, "std": 45.0, "min": 50.0, "max": 350.0},
    "circumference_0": {"mean": 275.0, "std": 35.0, "min": 180.0, "max": 400.0},
    "circumference_50": {"mean": 230.0, "std": 30.0, "min": 140.0, "max": 340.0},
    "circumference_100": {"mean": 155.0, "std": 30.0, "min": 80.0, "max": 260.0},
}


class NormalizationReport:
    """Report of any issues or adjustments found during normalization."""

    def __init__(self):
        self.warnings: list[str] = []
        self.adjustments: list[str] = []
        self.is_valid: bool = True

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_adjustment(self, msg: str):
        self.adjustments.append(msg)

    def mark_invalid(self, msg: str):
        self.is_valid = False
        self.warnings.append(f"INVALID: {msg}")

    def __str__(self) -> str:
        lines = []
        if self.warnings:
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"  ⚠ {w}")
        if self.adjustments:
            lines.append("Adjustments:")
            for a in self.adjustments:
                lines.append(f"  🔧 {a}")
        if not lines:
            lines.append("✅ All measurements within expected ranges.")
        return "\n".join(lines)


class MeasurementNormalizer:
    """Validates and normalizes patient measurements.
    
    Performs:
    - Z-score outlier detection against population statistics
    - Inter-measurement consistency checks
    - Optional infill for missing elliptical diameters (estimate from circumference)
    """

    def __init__(self, z_threshold: float = 2.5):
        """
        Args:
            z_threshold: Number of standard deviations to flag as outlier.
        """
        self.z_threshold = z_threshold

    def _z_score(self, value: float, stat_key: str) -> Optional[float]:
        """Compute z-score against population statistics."""
        stats = POPULATION_STATS.get(stat_key)
        if stats is None:
            return None
        return (value - stats["mean"]) / stats["std"]

    def _check_outliers(self, measurements: StumpMeasurements, report: NormalizationReport):
        """Flag measurements that are statistical outliers."""
        checks = [
            ("residual_limb_length", measurements.residual_limb_length),
            ("circumference_0", measurements.circumference_0),
            ("circumference_50", measurements.circumference_50),
            ("circumference_100", measurements.circumference_100),
        ]
        for key, value in checks:
            z = self._z_score(value, key)
            if z is not None and abs(z) > self.z_threshold:
                report.add_warning(
                    f"{key} = {value:.1f}mm (z-score: {z:.1f}) "
                    f"is an outlier — verify measurement"
                )

    def _check_taper_monotonicity(self, measurements: StumpMeasurements, report: NormalizationReport):
        """Verify circumferences generally decrease from proximal to distal."""
        circs = [
            measurements.circumference_0,
            measurements.circumference_25,
            measurements.circumference_50,
            measurements.circumference_75,
            measurements.circumference_100,
        ]
        for i in range(len(circs) - 1):
            if circs[i + 1] > circs[i]:
                pct_increase = (circs[i + 1] - circs[i]) / circs[i] * 100
                report.add_warning(
                    f"Non-monotonic taper: circumference at {(i+1)*25}% "
                    f"({circs[i+1]:.1f}mm) > {i*25}% ({circs[i]:.1f}mm) "
                    f"(+{pct_increase:.1f}%). Possible edema or measurement error."
                )

    def _check_diameter_consistency(self, measurements: StumpMeasurements, report: NormalizationReport):
        """Verify elliptical diameters are consistent with circumferences."""
        stations = [
            (0, measurements.major_diameter_0, measurements.minor_diameter_0, measurements.circumference_0),
            (50, measurements.major_diameter_50, measurements.minor_diameter_50, measurements.circumference_50),
            (100, measurements.major_diameter_100, measurements.minor_diameter_100, measurements.circumference_100),
        ]
        for station, major, minor, circ in stations:
            a, b = major / 2, minor / 2
            h = ((a - b) ** 2) / ((a + b) ** 2)
            estimated_circ = math.pi * (a + b) * (1 + (3 * h) / (10 + math.sqrt(4 - 3 * h)))
            deviation_pct = abs(estimated_circ - circ) / circ * 100
            if deviation_pct > 15:
                report.add_warning(
                    f"Station {station}%: ellipse circumference ({estimated_circ:.1f}mm) "
                    f"differs from measured circumference ({circ:.1f}mm) "
                    f"by {deviation_pct:.1f}%. Check diameters."
                )

    def _check_eccentricity(self, measurements: StumpMeasurements, report: NormalizationReport):
        """Flag unusually eccentric cross-sections."""
        stations = [
            (0, measurements.major_diameter_0, measurements.minor_diameter_0),
            (50, measurements.major_diameter_50, measurements.minor_diameter_50),
            (100, measurements.major_diameter_100, measurements.minor_diameter_100),
        ]
        for station, major, minor in stations:
            if major > 0 and minor > 0:
                ratio = minor / major
                if ratio < 0.5:
                    report.add_warning(
                        f"Station {station}%: cross-section is unusually elliptical "
                        f"(minor/major = {ratio:.2f}). Verify measurement."
                    )

    def validate(self, measurements: StumpMeasurements) -> NormalizationReport:
        """Run all validation checks on a measurement set.
        
        Returns:
            NormalizationReport with warnings and validity status.
        """
        report = NormalizationReport()
        self._check_outliers(measurements, report)
        self._check_taper_monotonicity(measurements, report)
        self._check_diameter_consistency(measurements, report)
        self._check_eccentricity(measurements, report)
        return report
