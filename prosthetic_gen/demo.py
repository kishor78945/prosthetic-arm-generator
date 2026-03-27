"""
Prosthetic Socket Generator — Demo Script
============================================
End-to-end demonstration: measurements → parametric socket + forearm + hand → export

Usage:
    python -m prosthetic_gen.demo
"""

import os
import sys
import time


def main():
    print("=" * 60)
    print("  Prosthetic Arm Generator — Full Demo")
    print("  Phase 1: Socket  |  Phase 2: Forearm + Hand")
    print("=" * 60)

    # Step 1: Create synthetic measurements
    print("\n[1/7] Creating synthetic patient measurements...")
    from prosthetic_gen.measurement_input.schema import create_synthetic_measurements
    measurements = create_synthetic_measurements(
        limb_length=180.0,
        proximal_circ=280.0,
        distal_circ=160.0,
        taper_exponent=1.2,
        eccentricity=0.1,
    )
    print(f"  Residual limb length: {measurements.residual_limb_length} mm")
    print(f"  Proximal circ: {measurements.circumference_0:.1f} mm")
    print(f"  Distal circ: {measurements.circumference_100:.1f} mm")
    print(f"  Contralateral arm: {measurements.contralateral_arm_length} mm")

    # Step 2: Validate measurements
    print("\n[2/7] Validating measurements...")
    from prosthetic_gen.measurement_input.normalizer import MeasurementNormalizer
    normalizer = MeasurementNormalizer()
    report = normalizer.validate(measurements)
    print(f"  {report}")

    # Step 3: Configure constraints
    print("\n[3/7] Configuring constraints...")
    from prosthetic_gen.parametric_engine.constraints import SocketConstraints
    constraints = SocketConstraints()
    print(f"  Socket wall: {constraints.nominal_wall_thickness} mm")
    print(f"  Forearm length: {constraints.forearm_length} mm")
    print(f"  Palm: {constraints.palm_width}×{constraints.palm_length}×{constraints.palm_thickness} mm")
    print(f"  Middle finger: {constraints.middle_finger_length} mm")
    print(f"  Grip angle: {constraints.grip_angle_deg}°")

    # Step 4: Check for CadQuery
    try:
        import cadquery as cq
    except ImportError:
        print("\n  ❌ CadQuery not installed. Run: pip install cadquery")
        return

    # Step 5: Generate full assembly
    print("\n[4/7] Generating socket...")
    from prosthetic_gen.parametric_engine.assembler import ProstheticAssembler
    assembler = ProstheticAssembler(measurements, constraints)

    start = time.time()
    socket = assembler.generate_socket()
    t1 = time.time()
    print(f"  ✅ Socket generated in {t1 - start:.2f}s")

    print("\n[5/7] Generating forearm tube...")
    forearm = assembler.generate_forearm()
    t2 = time.time()
    print(f"  ✅ Forearm generated in {t2 - t1:.2f}s")

    print("\n[6/7] Generating articulated hand...")
    hand = assembler.generate_hand()
    t3 = time.time()
    print(f"  ✅ Hand generated in {t3 - t2:.2f}s")

    print("\n  Assembling full arm...")
    full_arm = assembler.assemble()
    t4 = time.time()
    print(f"  ✅ Assembly complete in {t4 - t3:.2f}s")
    print(f"  Total generation time: {t4 - start:.2f}s")

    # Step 7: Export
    print("\n[7/7] Exporting to STL / STEP / GLB...")
    output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    os.makedirs(output_dir, exist_ok=True)

    from prosthetic_gen.parametric_engine.exporter import MeshExporter
    exporter = MeshExporter(output_dir=output_dir)

    # Export full assembly
    paths = exporter.export_all(full_arm, base_name="full_arm")
    print(f"\n  Full arm assembly:")
    for fmt, path in paths.items():
        size_kb = os.path.getsize(path) / 1024
        print(f"    {fmt.upper()}: {path} ({size_kb:.1f} KB)")

    # Also export individual components
    components = assembler.generate_components_separate()
    for name, comp in components.items():
        comp_paths = exporter.export_all(comp, base_name=name)
        print(f"\n  {name.title()} component:")
        for fmt, path in comp_paths.items():
            size_kb = os.path.getsize(path) / 1024
            print(f"    {fmt.upper()}: {path} ({size_kb:.1f} KB)")

    # Mesh stats
    stl_path = paths["stl"]
    stats = exporter.get_mesh_stats(stl_path)
    print(f"\n  Assembly mesh stats:")
    print(f"    Vertices: {stats['vertices']}")
    print(f"    Faces: {stats['faces']}")
    print(f"    Watertight: {stats['is_watertight']}")
    if stats['volume_mm3']:
        print(f"    Volume: {stats['volume_mm3']:.0f} mm³")

    print("\n" + "=" * 60)
    print("  Demo complete!")
    print(f"  Output files in: {os.path.abspath(output_dir)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
