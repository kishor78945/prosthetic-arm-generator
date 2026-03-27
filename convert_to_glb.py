"""Convert assembly STL to GLB and apply texture for browser viewing."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import trimesh

output_dir = os.path.join(os.path.dirname(__file__), "output", "phase4_visual")

# Load the assembly STL
print("Loading assembly STL...")
mesh = trimesh.load(os.path.join(output_dir, "assembly.stl"))
if isinstance(mesh, trimesh.Scene):
    mesh = trimesh.util.concatenate(mesh.dump())

print(f"  Vertices: {len(mesh.vertices)}")
print(f"  Faces: {len(mesh.faces)}")
print(f"  Bounds: {mesh.extents}")

# Export plain GLB
glb_path = os.path.join(output_dir, "assembly.glb")
mesh.export(glb_path, file_type="glb")
print(f"\nPlain GLB: {os.path.getsize(glb_path)/1024:.0f} KB")

# Apply skin texture
print("\nApplying skin texture...")
from prosthetic_gen.texture_synthesis.texturizer import Texturizer
texturizer = Texturizer()
textured_path = os.path.join(output_dir, "assembly_skin.glb")
texturizer.apply(glb_path, material="skin", skin_tone="medium", output_path=textured_path)
print(f"Skin GLB: {os.path.getsize(textured_path)/1024:.0f} KB")

# Apply metallic texture
print("Applying metallic texture...")
metallic_path = os.path.join(output_dir, "assembly_metallic.glb")
texturizer.apply(glb_path, material="metallic", output_path=metallic_path)
print(f"Metallic GLB: {os.path.getsize(metallic_path)/1024:.0f} KB")

# Also export individual components as GLB
for name in ["socket", "forearm", "hand"]:
    stl_file = os.path.join(output_dir, f"{name}.stl")
    glb_file = os.path.join(output_dir, f"{name}.glb")
    m = trimesh.load(stl_file)
    if isinstance(m, trimesh.Scene):
        m = trimesh.util.concatenate(m.dump())
    m.export(glb_file, file_type="glb")
    print(f"{name} GLB: {os.path.getsize(glb_file)/1024:.0f} KB")

print("\nDone!")
