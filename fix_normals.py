"""Fix normals and re-export GLBs with proper vertex normals."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trimesh
import numpy as np

output_dir = os.path.join(os.path.dirname(__file__), "output", "phase4_visual")

for name in ["assembly", "socket", "forearm", "hand"]:
    stl_path = os.path.join(output_dir, f"{name}.stl")
    if not os.path.exists(stl_path):
        continue
    
    mesh = trimesh.load(stl_path)
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(mesh.dump())
    
    # Fix normals to be outward-facing
    mesh.fix_normals()
    
    # Set a nice skin color
    mesh.visual.face_colors = np.tile([230, 200, 180, 255], (len(mesh.faces), 1))
    
    # Export GLB with corrected normals
    glb_path = os.path.join(output_dir, f"{name}.glb")
    mesh.export(glb_path, file_type="glb")
    print(f"{name}: {len(mesh.vertices)} verts, {len(mesh.faces)} faces -> {os.path.getsize(glb_path)/1024:.0f} KB")

# Also re-export textured versions
from prosthetic_gen.texture_synthesis.texturizer import Texturizer
texturizer = Texturizer()

# Skin
skin_path = os.path.join(output_dir, "assembly_skin.glb")
texturizer.apply(os.path.join(output_dir, "assembly.glb"), material="skin", skin_tone="medium", output_path=skin_path)
print(f"skin: {os.path.getsize(skin_path)/1024:.0f} KB")

# Metallic
met_path = os.path.join(output_dir, "assembly_metallic.glb")
texturizer.apply(os.path.join(output_dir, "assembly.glb"), material="metallic", output_path=met_path)
print(f"metallic: {os.path.getsize(met_path)/1024:.0f} KB")

print("\nDone! All GLBs re-exported with fixed normals.")
