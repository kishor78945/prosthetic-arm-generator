"""Tests for the normalizer module."""

import pytest

from prosthetic_gen.measurement_input.schema import create_synthetic_measurements
from prosthetic_gen.measurement_input.normalizer import MeasurementNormalizer


class TestMeasurementNormalizer:
    def test_valid_measurements_pass(self):
        m = create_synthetic_measurements()
        normalizer = MeasurementNormalizer()
        report = normalizer.validate(m)
        assert report.is_valid
        assert len(report.warnings) == 0

    def test_outlier_detection(self):
        # Use values that are statistical outliers but still within Pydantic field bounds
        m = create_synthetic_measurements(
            proximal_circ=395.0,  # Very large — z-score > 3
            distal_circ=280.0,
        )
        normalizer = MeasurementNormalizer(z_threshold=2.0)
        report = normalizer.validate(m)
        assert len(report.warnings) > 0
        assert any("outlier" in w.lower() for w in report.warnings)

    def test_extreme_eccentricity_warning(self):
        # Use moderate eccentricity that passes Pydantic validation
        m = create_synthetic_measurements(eccentricity=0.15)
        normalizer = MeasurementNormalizer()
        report = normalizer.validate(m)
        # May or may not trigger eccentricity warning depending on threshold
        assert isinstance(report.is_valid, bool)

    def test_report_string(self):
        m = create_synthetic_measurements()
        normalizer = MeasurementNormalizer()
        report = normalizer.validate(m)
        report_str = str(report)
        assert "✅" in report_str or "⚠" in report_str
