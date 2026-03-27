"""Tests for the measurement schema and synthetic data factory."""

import pytest
import math

from prosthetic_gen.measurement_input.schema import (
    StumpMeasurements,
    EllipticalProfile,
    LoadZone,
    create_synthetic_measurements,
)


class TestEllipticalProfile:
    def test_circular_profile(self):
        p = EllipticalProfile(major_diameter=80.0, minor_diameter=80.0)
        expected_circ = math.pi * 80.0
        assert abs(p.circumference_approx - expected_circ) < 0.1
        assert abs(p.eccentricity) < 0.01

    def test_elliptical_profile(self):
        p = EllipticalProfile(major_diameter=90.0, minor_diameter=70.0)
        assert p.eccentricity > 0.0
        assert p.eccentricity < 1.0
        assert p.circumference_approx > 0

    def test_invalid_diameter(self):
        with pytest.raises(ValueError):
            EllipticalProfile(major_diameter=-10.0, minor_diameter=50.0)


class TestStumpMeasurements:
    def test_valid_measurements(self):
        m = create_synthetic_measurements()
        assert m.residual_limb_length == 180.0
        assert m.circumference_0 > m.circumference_100

    def test_taper_validation_passes(self):
        m = create_synthetic_measurements()
        circs = [m.circumference_0, m.circumference_25, m.circumference_50,
                 m.circumference_75, m.circumference_100]
        for i in range(len(circs) - 1):
            assert circs[i] >= circs[i + 1]

    def test_taper_validation_fails_on_increase(self):
        with pytest.raises(ValueError, match="exceeds circumference"):
            StumpMeasurements(
                residual_limb_length=180.0,
                circumference_0=200.0,
                circumference_25=250.0,  # Invalid: increases
                circumference_50=230.0,
                circumference_75=210.0,
                circumference_100=160.0,
                major_diameter_0=70.0, minor_diameter_0=60.0,
                major_diameter_50=75.0, minor_diameter_50=70.0,
                major_diameter_100=55.0, minor_diameter_100=48.0,
            )

    def test_get_profile_at_measured_station(self):
        m = create_synthetic_measurements()
        p = m.get_profile_at(0)
        assert p.major_diameter == m.major_diameter_0
        assert p.minor_diameter == m.minor_diameter_0

    def test_get_profile_at_interpolated_station(self):
        m = create_synthetic_measurements()
        p25 = m.get_profile_at(25)
        expected_major = (m.major_diameter_0 + m.major_diameter_50) / 2
        assert abs(p25.major_diameter - expected_major) < 0.01

    def test_get_all_profiles(self):
        m = create_synthetic_measurements()
        profiles = m.get_all_profiles()
        assert len(profiles) == 5
        assert all(s in profiles for s in [0, 25, 50, 75, 100])

    def test_invalid_station(self):
        m = create_synthetic_measurements()
        with pytest.raises(ValueError):
            m.get_profile_at(33)

    def test_load_zones(self):
        m = create_synthetic_measurements()
        assert m.has_load_zone(LoadZone.OLECRANON)
        assert m.has_load_zone(LoadZone.DISTAL_END)
        assert not m.has_load_zone(LoadZone.BICIPITAL_TENDON)


class TestLoadZone:
    def test_flag_combination(self):
        combined = LoadZone.OLECRANON | LoadZone.MEDIAL_EPICONDYLE
        assert LoadZone.OLECRANON in combined
        assert LoadZone.MEDIAL_EPICONDYLE in combined
        assert LoadZone.DISTAL_END not in combined


class TestSyntheticFactory:
    def test_default_synthetic(self):
        m = create_synthetic_measurements()
        assert m.residual_limb_length == 180.0
        assert m.circumference_0 == 280.0

    def test_custom_synthetic(self):
        m = create_synthetic_measurements(
            limb_length=200.0,
            proximal_circ=300.0,
            distal_circ=180.0,
        )
        assert m.residual_limb_length == 200.0
        assert m.circumference_0 == 300.0
        assert m.circumference_100 == 180.0

    def test_synthetic_taper_shapes(self):
        # Linear taper
        m_linear = create_synthetic_measurements(taper_exponent=1.0)
        # Concave taper
        m_concave = create_synthetic_measurements(taper_exponent=2.0)
        # Midpoint circumference should differ
        assert m_linear.circumference_50 != m_concave.circumference_50

    def test_synthetic_eccentricity(self):
        m_circular = create_synthetic_measurements(eccentricity=0.0)
        assert abs(m_circular.major_diameter_0 - m_circular.minor_diameter_0) < 0.1

        m_elliptical = create_synthetic_measurements(eccentricity=0.1)
        assert m_elliptical.major_diameter_0 > m_elliptical.minor_diameter_0
