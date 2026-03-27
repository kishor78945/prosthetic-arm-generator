"""Render prosthetic arm assembly as an image using trimesh."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import Image
import trimesh

output_dir = os.path.join(os.path.dirname(__file__), "output", "phase4_visual")

# Load mesh
print("Loading assembly...")
mesh = trimesh.load(os.path.join(output_dir, "assembly.stl"))
if isinstance(mesh, trimesh.Scene):
    mesh = trimesh.util.concatenate(mesh.dump())

print(f"  Vertices: {len(mesh.vertices)}")
print(f"  Faces: {len(mesh.faces)}")
print(f"  Bounds: {mesh.extents}")
print(f"  Watertight: {mesh.is_watertight}")

# Fix normals
mesh.fix_normals()

# Apply a nice skin-tone color
mesh.visual.face_colors = [220, 190, 170, 255]

# Create a scene for rendering
scene = trimesh.Scene(geometry={"arm": mesh})

# Try to render using pyrender or built-in
try:
    # Render using trimesh's built-in export capabilities
    # Save as a rotated view from the side
    png_bytes = scene.save_image(resolution=(1920, 1080), visible=False)
    img_path = os.path.join(output_dir, "assembly_render.png")
    with open(img_path, 'wb') as f:
        f.write(png_bytes)
    print(f"\nRendered image: {img_path}")
    print(f"Size: {os.path.getsize(img_path)/1024:.0f} KB")
except Exception as e:
    print(f"Render failed (pyrender/pyglet needed): {e}")
    
    # Fallback: generate a depth/normal map visualization
    print("\nGenerating depth visualization...")
    from trimesh import viewer
    
    # Alternative: just report stats and let the user view the GLB
    print("\n=== Assembly Statistics ===")
    print(f"  Total vertices: {len(mesh.vertices)}")
    print(f"  Total faces: {len(mesh.faces)}")
    print(f"  Dimensions: {mesh.extents[0]:.1f} x {mesh.extents[1]:.1f} x {mesh.extents[2]:.1f} mm")
    print(f"  Volume: {mesh.volume:.0f} mm³")
    print(f"  Surface area: {mesh.area:.0f} mm²")
    print(f"  Is watertight: {mesh.is_watertight}")
    print(f"  Is convex: {mesh.is_convex}")
    
    # Generate a simple cross-section visualization
    print("\n=== Cross-section at Z-midpoint ===")
    z_mid = (mesh.bounds[0][2] + mesh.bounds[1][2]) / 2
    section = mesh.section(plane_origin=[0, 0, z_mid], plane_normal=[0, 0, 1])
    if section is not None:
        path = section.to_planar()[0]
        print(f"  Cross-section at Z={z_mid:.0f}mm")
        print(f"  Cross-section area: {path.area:.1f} mm²")
    
    # Also export individual component stats
    for name in ["socket", "forearm", "hand"]:
        m = trimesh.load(os.path.join(output_dir, f"{name}.stl"))
        if isinstance(m, trimesh.Scene):
            m = trimesh.util.concatenate(m.dump())
        print(f"\n  {name}: {len(m.vertices)} verts, {len(m.faces)} faces, "
              f"{m.extents[0]:.0f}×{m.extents[1]:.0f}×{m.extents[2]:.0f} mm")

print("\nDone!")
print(f"\nFiles available for viewing:")
for f in sorted(os.listdir(output_dir)):
    if f.endswith(('.glb', '.stl', '.png')):
        size = os.path.getsize(os.path.join(output_dir, f)) / 1024
        print(f"  {f:40s} {size:8.0f} KB")
