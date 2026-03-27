"""
Offline test for Phase 3 — Lightweight Procedural Texture Pipeline.
Run: python test_texture_pipeline.py
"""

import sys
import os
import traceback
from pathlib import Path

# Ensure project is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

OUT_DIR = Path("output/texture_test")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def header(title):
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print(f"{'=' * 50}")


# ── TEST 1: GPU Detection ────────────────────────────
def test_gpu():
    header("TEST 1: GPU Detection")
    from prosthetic_gen.texture_synthesis.texturizer import Texturizer

    info = Texturizer.check_gpu()
    print(f"  CUDA available : {info['cuda_available']}")
    print(f"  GPU name       : {info['gpu_name']}")
    print(f"  VRAM           : {info['vram_gb']} GB")
    print(f"  Sufficient     : {info['sufficient']}")
    return True  # Always passes — GPU is optional for lightweight textures


# ── TEST 2: Arm Generation + GLB Export ───────────────
def test_generate_arm():
    header("TEST 2: Arm Generation + GLB Export")
    from prosthetic_gen.parametric_engine.assembler import ProstheticAssembler
    from prosthetic_gen.measurement_input.schema import create_synthetic_measurements
    import cadquery as cq
    import trimesh

    measurements = create_synthetic_measurements(
        limb_length=150,
        proximal_circ=280,
        distal_circ=160,
    )
    assembler = ProstheticAssembler(measurements)
    assembly = assembler.assemble()

    # CadQuery -> STL -> trimesh -> GLB
    stl_path = str(OUT_DIR / "test_arm.stl")
    glb_path = str(OUT_DIR / "test_arm.glb")
    cq.exporters.export(assembly, stl_path, exportType="STL")
    mesh = trimesh.load(stl_path)
    mesh.export(glb_path)

    assert os.path.exists(glb_path), "GLB file not created"
    fsize = os.path.getsize(glb_path) / 1024
    print(f"  GLB exported: {glb_path} ({fsize:.1f} KB)")
    return True


# ── TEST 3: Texture Map Generation ───────────────────
def test_texture_maps():
    header("TEST 3: Texture Map Generation")
    from prosthetic_gen.texture_synthesis.texturizer import (
        Texturizer, MaterialPreset, SkinTone,
    )

    texturizer = Texturizer(texture_size=512)
    materials = list(MaterialPreset)
    skin_tones = list(SkinTone)

    for mat in materials:
        for tone in skin_tones:
            if tone == SkinTone.CUSTOM:
                custom_color = (180, 120, 90)
            else:
                custom_color = None

            img = texturizer._create_texture_map(mat, tone, custom_color)
            fname = f"tex_{mat.value}_{tone.value}.png"
            img.save(str(OUT_DIR / fname))
            print(f"  ✓ {fname} ({img.size[0]}x{img.size[1]})")

    return True


# ── TEST 4: Full Texture Application to GLB ──────────
def test_texture_pipeline():
    header("TEST 4: Full Texture Application to GLB")
    from prosthetic_gen.texture_synthesis.texturizer import (
        Texturizer, MaterialPreset, SkinTone,
    )

    glb_path = str(OUT_DIR / "test_arm.glb")
    if not os.path.exists(glb_path):
        print("  ⚠ Skipping — no GLB from test 2")
        return False

    texturizer = Texturizer.from_pretrained()
    assert texturizer.is_available(), "Texturizer not available"

    presets = [
        (MaterialPreset.SKIN, SkinTone.MEDIUM, None, "skin_medium"),
        (MaterialPreset.SKIN, SkinTone.DARK, None, "skin_dark"),
        (MaterialPreset.PLASTIC, SkinTone.MEDIUM, None, "plastic"),
        (MaterialPreset.CARBON_FIBER, SkinTone.MEDIUM, None, "carbon_fiber"),
        (MaterialPreset.METALLIC, SkinTone.MEDIUM, None, "metallic"),
        (MaterialPreset.SKIN, SkinTone.CUSTOM, (180, 120, 90), "skin_custom"),
    ]

    for material, tone, custom, label in presets:
        out_path = str(OUT_DIR / f"textured_{label}.glb")
        result = texturizer.apply(
            mesh_path=glb_path,
            material=material,
            skin_tone=tone,
            custom_color=custom,
            output_path=out_path,
        )
        fsize = os.path.getsize(out_path) / 1024
        print(f"  ✓ {label}: {fsize:.1f} KB")

    return True


# ── MAIN ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🧪 Prosthetic Arm — Phase 3 Texture Pipeline Test")
    print("=" * 50)

    results = {}
    tests = [
        ("gpu", test_gpu),
        ("generation", test_generate_arm),
        ("texture_maps", test_texture_maps),
        ("texture_pipeline", test_texture_pipeline),
    ]

    for name, fn in tests:
        try:
            results[name] = fn()
        except Exception as e:
            print(f"  ❌ {name} FAILED: {e}")
            traceback.print_exc()
            results[name] = False

    # Summary
    header("Results Summary")
    all_pass = True
    for name, ok in results.items():
        icon = "✅" if ok else "❌"
        print(f"  {name:<20}: {icon} {'PASS' if ok else 'FAIL'}")
        if not ok:
            all_pass = False

    if all_pass:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n⚠️  SOME TESTS FAILED")
        sys.exit(1)
