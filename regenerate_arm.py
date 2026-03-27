"""Regenerate all prosthetic arm components and re-export to GLB."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import traceback
import trimesh
import numpy as np

output_dir = os.path.join(os.path.dirname(__file__), "output", "phase4_visual")
os.makedirs(output_dir, exist_ok=True)

print("=" * 60)
print("REGENERATING PROSTHETIC ARM WITH FIXED THUMB")
print("=" * 60)

# Step 1: Generate geometry with CadQuery
print("\n[1/4] Generating CadQuery geometry...")
from prosthetic_gen.measurement_input.schema import create_synthetic_measurements
from prosthetic_gen.parametric_engine.constraints import SocketConstraints
from prosthetic_gen.parametric_engine.assembler import ProstheticAssembler

measurements = create_synthetic_measurements()
constraints = SocketConstraints()
assembler = ProstheticAssembler(measurements, constraints)

# Generate each component
print("  Generating socket...")
assembler.generate_socket()
print("  Generating forearm...")
assembler.generate_forearm()
print("  Generating hand (with fixed thumb)...")
assembler.generate_hand()
print("  Assembling...")
assembler.assemble()
print("  [OK] Assembly complete")

# Step 2: Export STL for each component
print("\n[2/4] Exporting STL files...")
import cadquery as cq

components = assembler.generate_components_separate()
for name, solid in components.items():
    stl_path = os.path.join(output_dir, f"{name}.stl")
    cq.exporters.export(solid, stl_path, exportType="STL", tolerance=0.02)
    size = os.path.getsize(stl_path) / 1024
    print(f"  {name}.stl: {size:.0f} KB")

# Assembly
assembly_stl = os.path.join(output_dir, "assembly.stl")
cq.exporters.export(assembler.assembly, assembly_stl, exportType="STL", tolerance=0.02)
size = os.path.getsize(assembly_stl) / 1024
print(f"  assembly.stl: {size:.0f} KB")

# Step 3: Convert to GLB with fixed normals
print("\n[3/4] Converting to GLB with fixed normals...")
for name in ["assembly", "socket", "forearm", "hand"]:
    stl_path = os.path.join(output_dir, f"{name}.stl")
    mesh = trimesh.load(stl_path)
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(mesh.dump())
    
    mesh.fix_normals()
    mesh.visual.face_colors = np.tile([230, 200, 180, 255], (len(mesh.faces), 1))
    
    glb_path = os.path.join(output_dir, f"{name}.glb")
    mesh.export(glb_path, file_type="glb")
    print(f"  {name}.glb: {len(mesh.vertices)} verts, {len(mesh.faces)} faces, "
          f"{os.path.getsize(glb_path)/1024:.0f} KB")

# Step 4: Apply textures
print("\n[4/4] Applying textures...")
try:
    from prosthetic_gen.texture_synthesis.texturizer import Texturizer
    texturizer = Texturizer()
    
    skin_path = os.path.join(output_dir, "assembly_skin.glb")
    texturizer.apply(os.path.join(output_dir, "assembly.glb"), 
                     material="skin", skin_tone="medium", output_path=skin_path)
    print(f"  assembly_skin.glb: {os.path.getsize(skin_path)/1024:.0f} KB")
    
    met_path = os.path.join(output_dir, "assembly_metallic.glb")
    texturizer.apply(os.path.join(output_dir, "assembly.glb"),
                     material="metallic", output_path=met_path)
    print(f"  assembly_metallic.glb: {os.path.getsize(met_path)/1024:.0f} KB")
except Exception as e:
    print(f"  Texturing error: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("DONE — Open http://localhost:8765/view2.html to see results")
print("=" * 60)
