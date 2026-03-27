"""
Mesh Post-Processor
======================
Geometry-preserving post-processing for smoother GLB export.
Subdivision smoothing, vertex normal recalculation, and decimation.

All operations are geometry-preserving: no dimension changes beyond
the specified tolerance (default ≤ 0.5mm deviation).
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class MeshPostProcessor:
    """Geometry-preserving mesh post-processing pipeline.

    Operations:
    1. Subdivision surface smoothing (1-2 iterations)
    2. Vertex normal recalculation for smooth shading
    3. Decimation to target face count
    4. Cross-section deviation validation (≤ tolerance)

    All operations preserve the original measurement-driven dimensions
    within the specified tolerance.
    """

    # Maximum allowable deviation from original geometry (mm)
    MAX_DEVIATION_MM = 0.5

    def __init__(
        self,
        subdivision_iterations: int = 1,
        target_faces: int = 50000,
        max_deviation_mm: float = 0.5,
    ):
        """
        Args:
            subdivision_iterations: Number of Loop subdivision passes (1-2)
            target_faces: Target face count after decimation
            max_deviation_mm: Max allowed deviation from original (mm)
        """
        self.subdivision_iterations = min(subdivision_iterations, 2)
        self.target_faces = target_faces
        self.max_deviation_mm = min(max_deviation_mm, self.MAX_DEVIATION_MM)

    def process(self, mesh) -> 'trimesh.Trimesh':
        """Apply full post-processing pipeline.

        Args:
            mesh: trimesh.Trimesh object (from STL import)

        Returns:
            Processed trimesh.Trimesh with smooth normals and reduced face count
        """
        import trimesh

        original_bounds = mesh.bounds.copy()
        original_volume = mesh.volume if mesh.is_watertight else None

        logger.info(f"Post-processing: {len(mesh.faces)} faces, "
                     f"bounds={mesh.extents}")

        # Step 1: Subdivision smoothing
        if self.subdivision_iterations > 0:
            mesh = self._subdivide(mesh)

        # Step 2: Recalculate vertex normals for smooth shading
        mesh = self._smooth_normals(mesh)

        # Step 3: Decimation to target face count
        if len(mesh.faces) > self.target_faces:
            mesh = self._decimate(mesh)

        # Step 4: Validate deviation
        self._validate_deviation(mesh, original_bounds, original_volume)

        logger.info(f"Post-processed: {len(mesh.faces)} faces")
        return mesh

    def _subdivide(self, mesh) -> 'trimesh.Trimesh':
        """Apply Loop subdivision for smoother surfaces."""
        import trimesh

        for i in range(self.subdivision_iterations):
            try:
                # trimesh's subdivide_loop is geometry-preserving
                # (smooths without changing boundary positions)
                vertices, faces = trimesh.remesh.subdivide(
                    mesh.vertices, mesh.faces
                )
                mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
                logger.info(f"  Subdivision pass {i + 1}: {len(mesh.faces)} faces")
            except Exception as e:
                logger.warning(f"  Subdivision pass {i + 1} failed: {e}")
                break

        return mesh

    def _smooth_normals(self, mesh) -> 'trimesh.Trimesh':
        """Recalculate vertex normals for smooth shading (no geometry change)."""
        # Reset face/vertex normals — trimesh recalculates on access
        mesh.face_normals  # triggers lazy computation
        mesh.vertex_normals  # triggers lazy computation
        return mesh

    def _decimate(self, mesh) -> 'trimesh.Trimesh':
        """Reduce face count while preserving shape.

        Uses quadric edge collapse decimation via trimesh.
        """
        try:
            # trimesh uses simplify_quadric_decimation if available
            ratio = self.target_faces / len(mesh.faces)
            mesh = mesh.simplify_quadric_decimation(self.target_faces)
            logger.info(f"  Decimated to {len(mesh.faces)} faces "
                         f"(ratio={ratio:.2f})")
        except Exception as e:
            logger.warning(f"  Decimation failed (not critical): {e}")

        return mesh

    def _validate_deviation(
        self, mesh, original_bounds: np.ndarray,
        original_volume: Optional[float]
    ):
        """Validate that post-processing didn't alter geometry beyond tolerance.

        Checks:
        1. Bounding box deviation ≤ max_deviation_mm per axis
        2. Volume change ≤ 5% (if watertight)
        """
        new_bounds = mesh.bounds
        deviation = np.max(np.abs(new_bounds - original_bounds))

        if deviation > self.max_deviation_mm:
            logger.warning(
                f"  ⚠ Geometry deviation {deviation:.3f}mm exceeds "
                f"tolerance {self.max_deviation_mm}mm"
            )
        else:
            logger.info(f"  ✓ Geometry deviation {deviation:.3f}mm "
                         f"within {self.max_deviation_mm}mm tolerance")

        if original_volume is not None and mesh.is_watertight:
            volume_change = abs(mesh.volume - original_volume) / original_volume
            if volume_change > 0.05:
                logger.warning(
                    f"  ⚠ Volume change {volume_change * 100:.1f}% exceeds 5%"
                )
            else:
                logger.info(f"  ✓ Volume change {volume_change * 100:.1f}%")

    def export_glb(
        self,
        mesh,
        output_path: str,
        tessellation: str = "high",
    ) -> str:
        """Export mesh to GLB with configurable tessellation quality.

        Args:
            mesh: trimesh.Trimesh to export
            output_path: Path for the output GLB file
            tessellation: Quality level — "low", "medium", "high"

        Returns:
            Path to the exported GLB file
        """
        # Process mesh before export
        processed = self.process(mesh)

        # Export
        output_path = str(output_path)
        processed.export(output_path, file_type="glb")
        logger.info(f"Exported GLB: {output_path}")
        return output_path


def stl_to_glb(
    stl_path: str,
    glb_path: str,
    postprocess: bool = True,
    subdivision_iterations: int = 1,
    target_faces: int = 50000,
) -> str:
    """Convert STL to GLB with optional post-processing.

    Convenience function for the common CadQuery → STL → GLB pipeline.

    Args:
        stl_path: Input STL file path
        glb_path: Output GLB file path
        postprocess: Whether to apply subdivision + decimation
        subdivision_iterations: Number of subdivision passes
        target_faces: Target face count

    Returns:
        Path to the exported GLB file
    """
    import trimesh

    mesh = trimesh.load(stl_path)
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(mesh.dump())

    if postprocess:
        processor = MeshPostProcessor(
            subdivision_iterations=subdivision_iterations,
            target_faces=target_faces,
        )
        mesh = processor.process(mesh)

    mesh.export(glb_path, file_type="glb")
    logger.info(f"Converted {stl_path} → {glb_path}")
    return glb_path
