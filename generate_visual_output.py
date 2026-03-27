"""
Generate and export improved prosthetic arm for visual inspection.
"""
import sys
import os
import logging

logging.basicConfig(level=logging.INFO)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prosthetic_gen.measurement_input.schema import create_synthetic_measurements
from prosthetic_gen.parametric_engine.assembler import ProstheticAssembler
import cadquery as cq

output_dir = os.path.join(os.path.dirname(__file__), "output", "phase4_visual")
os.makedirs(output_dir, exist_ok=True)

print("=" * 60)
print("Phase 4: Improved Geometry — Visual Output")
print("=" * 60)

# Create measurements
measurements = create_synthetic_measurements()

# Generate assembly
print("\n1. Generating prosthetic arm with improved geometry...")
assembler = ProstheticAssembler(measurements)
assembly = assembler.assemble()
print("   ✓ Assembly complete")

# Export STL (high tessellation)
stl_path = os.path.join(output_dir, "prosthetic_arm_improved.stl")
print(f"\n2. Exporting STL (high tessellation)...")
assembler.export_stl(stl_path, tessellation="high")
print(f"   ✓ STL: {stl_path}")
stl_size = os.path.getsize(stl_path) / 1024
print(f"   Size: {stl_size:.1f} KB")

# Export GLB with post-processing
glb_path = os.path.join(output_dir, "prosthetic_arm_improved.glb")
print(f"\n3. Exporting GLB with post-processing...")
assembler.export_glb(
    glb_path,
    tessellation="high",
    postprocess=True,
    subdivision_iterations=1,
    target_faces=50000,
)
print(f"   ✓ GLB: {glb_path}")
glb_size = os.path.getsize(glb_path) / 1024
print(f"   Size: {glb_size:.1f} KB")

# Also export individual components for comparison
print(f"\n4. Exporting individual components...")
components = assembler.generate_components_separate()
for name, comp in components.items():
    comp_stl = os.path.join(output_dir, f"{name}.stl")
    cq.exporters.export(comp, comp_stl, exportType="STL", tolerance=0.02)
    
    # Convert to GLB via trimesh
    import trimesh
    mesh = trimesh.load(comp_stl)
    comp_glb = os.path.join(output_dir, f"{name}.glb")
    mesh.export(comp_glb)
    size = os.path.getsize(comp_glb) / 1024
    print(f"   ✓ {name}: {size:.1f} KB")

# Also apply a texture to the improved geometry
print(f"\n5. Applying skin texture to improved geometry...")
from prosthetic_gen.texture_synthesis.texturizer import Texturizer
texturizer = Texturizer()
textured_path = os.path.join(output_dir, "prosthetic_arm_textured_skin.glb")
texturizer.apply(
    glb_path,
    material="skin",
    skin_tone="medium",
    output_path=textured_path,
)
tex_size = os.path.getsize(textured_path) / 1024
print(f"   ✓ Textured: {tex_size:.1f} KB")

# Metallic version
textured_metal_path = os.path.join(output_dir, "prosthetic_arm_textured_metallic.glb")
texturizer.apply(
    glb_path,
    material="metallic",
    output_path=textured_metal_path,
)
tex_metal_size = os.path.getsize(textured_metal_path) / 1024
print(f"   ✓ Metallic: {tex_metal_size:.1f} KB")

print("\n" + "=" * 60)
print("✅ All outputs generated!")
print(f"Output directory: {output_dir}")
print("=" * 60)
