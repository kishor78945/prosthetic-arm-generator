"""Diagnostic: test each component individually."""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prosthetic_gen.measurement_input.schema import create_synthetic_measurements
from prosthetic_gen.parametric_engine.constraints import SocketConstraints
import cadquery as cq

measurements = create_synthetic_measurements()
constraints = SocketConstraints()
output_dir = os.path.join(os.path.dirname(__file__), "output", "phase4_visual")
os.makedirs(output_dir, exist_ok=True)

# Test 1: Socket
print("=== SOCKET ===")
try:
    from prosthetic_gen.parametric_engine.socket_generator import SocketGenerator
    gen = SocketGenerator(measurements, constraints)
    socket = gen.generate_simple()
    stl = os.path.join(output_dir, "socket.stl")
    cq.exporters.export(socket, stl, exportType="STL", tolerance=0.1)
    print(f"  OK: {os.path.getsize(stl)/1024:.0f} KB")
except Exception as e:
    print(f"  FAIL: {e}")
    traceback.print_exc()

# Test 2: Forearm
print("\n=== FOREARM ===")
try:
    from prosthetic_gen.parametric_engine.forearm_generator import ForearmGenerator
    gen = ForearmGenerator(measurements, constraints)
    forearm = gen.generate()
    stl = os.path.join(output_dir, "forearm.stl")
    cq.exporters.export(forearm, stl, exportType="STL", tolerance=0.1)
    print(f"  OK: {os.path.getsize(stl)/1024:.0f} KB")
except Exception as e:
    print(f"  FAIL: {e}")
    traceback.print_exc()

# Test 3: Hand
print("\n=== HAND ===")
try:
    from prosthetic_gen.parametric_engine.hand_generator import HandGenerator
    wrist_z = 300.0  # approximate
    gen = HandGenerator(constraints, wrist_z=wrist_z)
    hand = gen.generate()
    stl = os.path.join(output_dir, "hand.stl")
    cq.exporters.export(hand, stl, exportType="STL", tolerance=0.1)
    print(f"  OK: {os.path.getsize(stl)/1024:.0f} KB")
except Exception as e:
    print(f"  FAIL: {e}")
    traceback.print_exc()

# Test 4: Assembly
print("\n=== ASSEMBLY ===")
try:
    from prosthetic_gen.parametric_engine.assembler import ProstheticAssembler
    asm = ProstheticAssembler(measurements, constraints)
    assembly = asm.assemble()
    stl = os.path.join(output_dir, "assembly.stl")
    cq.exporters.export(assembly, stl, exportType="STL", tolerance=0.1)
    print(f"  OK: {os.path.getsize(stl)/1024:.0f} KB")
except Exception as e:
    print(f"  FAIL: {e}")
    traceback.print_exc()

print("\n=== DONE ===")
