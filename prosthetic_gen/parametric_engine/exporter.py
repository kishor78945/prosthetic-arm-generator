"""
Mesh Exporter
===============
Export CadQuery solids to STL, STEP, and GLB formats.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional, Union

import cadquery as cq


class MeshExporter:
    """Export prosthetic socket geometry to multiple formats.
    
    Supported formats:
    - STEP (.step) — parametric CAD interchange, clinical standard
    - STL (.stl) — triangulated mesh for 3D printing / fabrication
    - GLB (.glb) — lightweight 3D for web viewers / Gradio preview
    """

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or tempfile.mkdtemp(prefix="prosthetic_")
        os.makedirs(self.output_dir, exist_ok=True)

    def export_step(
        self,
        workplane: cq.Workplane,
        filename: str = "socket.step",
    ) -> str:
        """Export to STEP format (parametric, editable by prosthetists).
        
        Args:
            workplane: CadQuery Workplane containing the socket
            filename: Output filename
            
        Returns:
            Full path to exported file
        """
        filepath = os.path.join(self.output_dir, filename)
        cq.exporters.export(workplane, filepath, cq.exporters.ExportTypes.STEP)
        return filepath

    def export_stl(
        self,
        workplane: cq.Workplane,
        filename: str = "socket.stl",
        tolerance: float = 0.1,
        angular_tolerance: float = 0.1,
    ) -> str:
        """Export to STL format (for 3D printing).
        
        Args:
            workplane: CadQuery Workplane containing the socket
            filename: Output filename
            tolerance: Linear tolerance for tessellation (mm)
            angular_tolerance: Angular tolerance (radians)
            
        Returns:
            Full path to exported file
        """
        filepath = os.path.join(self.output_dir, filename)
        cq.exporters.export(
            workplane,
            filepath,
            cq.exporters.ExportTypes.STL,
            tolerance=tolerance,
            angularTolerance=angular_tolerance,
        )
        return filepath

    def export_glb(
        self,
        workplane: cq.Workplane,
        filename: str = "socket.glb",
    ) -> str:
        """Export to GLB format (for web preview / Hunyuan3D-Paint input).
        
        GLB export requires tessellation to triangles, then conversion.
        Uses trimesh as an intermediary.
        
        Args:
            workplane: CadQuery Workplane containing the socket
            filename: Output filename
            
        Returns:
            Full path to exported file
        """
        import trimesh

        # First export to STL, then load with trimesh and re-export as GLB
        stl_path = self.export_stl(workplane, "_temp_for_glb.stl")
        mesh = trimesh.load(stl_path)

        filepath = os.path.join(self.output_dir, filename)
        mesh.export(filepath, file_type="glb")

        # Cleanup temp STL
        try:
            os.remove(stl_path)
        except OSError:
            pass

        return filepath

    def export_all(
        self,
        workplane: cq.Workplane,
        base_name: str = "socket",
    ) -> dict[str, str]:
        """Export to all supported formats.
        
        Args:
            workplane: CadQuery Workplane containing the socket
            base_name: Base filename (without extension)
            
        Returns:
            Dict mapping format name to file path
        """
        return {
            "step": self.export_step(workplane, f"{base_name}.step"),
            "stl": self.export_stl(workplane, f"{base_name}.stl"),
            "glb": self.export_glb(workplane, f"{base_name}.glb"),
        }

    def get_mesh_stats(self, stl_path: str) -> dict:
        """Get statistics about an exported mesh.
        
        Args:
            stl_path: Path to STL file
            
        Returns:
            Dict with face count, vertex count, volume, watertight status
        """
        import trimesh
        mesh = trimesh.load(stl_path)
        return {
            "vertices": len(mesh.vertices),
            "faces": len(mesh.faces),
            "volume_mm3": float(mesh.volume) if mesh.is_watertight else None,
            "is_watertight": mesh.is_watertight,
            "surface_area_mm2": float(mesh.area),
            "bounding_box": {
                "min": mesh.bounds[0].tolist(),
                "max": mesh.bounds[1].tolist(),
            },
        }
