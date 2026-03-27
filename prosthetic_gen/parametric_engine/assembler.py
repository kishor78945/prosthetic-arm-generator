"""
Prosthetic Arm Assembler
==========================
Combines socket, forearm, and hand into a unified prosthetic arm.
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional

import cadquery as cq

from ..measurement_input.schema import StumpMeasurements
from .constraints import SocketConstraints
from .socket_generator import SocketGenerator
from .forearm_generator import ForearmGenerator
from .hand_generator import HandGenerator

logger = logging.getLogger(__name__)


class ProstheticAssembler:
    """Assembles all prosthetic components into a single exportable model.

    Pipeline:
    1. Generate socket from patient measurements
    2. Generate forearm tube (attaches to socket distal end)
    3. Generate hand (attaches to forearm wrist connector)
    4. Union all components into one solid
    5. Export to STL/GLB with post-processing
    """

    # CadQuery tessellation tolerances for STL export
    TESSELLATION_QUALITY = {
        "low": 0.5,       # coarse — fast preview
        "medium": 0.1,    # default
        "high": 0.02,     # fine — production quality
    }

    def __init__(
        self,
        measurements: StumpMeasurements,
        constraints: Optional[SocketConstraints] = None,
    ):
        self.measurements = measurements
        self.constraints = constraints or SocketConstraints()
        self._socket: Optional[cq.Workplane] = None
        self._forearm: Optional[cq.Workplane] = None
        self._hand: Optional[cq.Workplane] = None
        self._assembly: Optional[cq.Workplane] = None

    def generate_socket(self) -> cq.Workplane:
        """Generate socket component."""
        gen = SocketGenerator(self.measurements, self.constraints)
        self._socket = gen.generate_simple()
        return self._socket

    def generate_forearm(self) -> cq.Workplane:
        """Generate forearm component."""
        gen = ForearmGenerator(self.measurements, self.constraints)
        self._forearm = gen.generate()
        self._forearm_gen = gen
        return self._forearm

    def generate_hand(self) -> cq.Workplane:
        """Generate hand component."""
        if not hasattr(self, '_forearm_gen'):
            raise RuntimeError("Generate forearm first to determine wrist position.")
        wrist_z = self._forearm_gen.get_distal_z()
        gen = HandGenerator(self.constraints, wrist_z=wrist_z)
        self._hand = gen.generate()
        return self._hand

    def assemble(self) -> cq.Workplane:
        """Generate all components and combine into one assembly.

        Returns:
            CadQuery Workplane with the complete prosthetic arm.
        """
        if self._socket is None:
            self.generate_socket()
        if self._forearm is None:
            self.generate_forearm()
        if self._hand is None:
            self.generate_hand()

        assembly = self._socket.union(self._forearm).union(self._hand)
        self._assembly = assembly
        return assembly

    def export_stl(
        self,
        output_path: str,
        tessellation: str = "high",
    ) -> str:
        """Export assembly to STL with configurable tessellation quality.

        Args:
            output_path: Path for the output STL file
            tessellation: Quality level — "low", "medium", "high"

        Returns:
            Path to the exported STL file
        """
        if self._assembly is None:
            self.assemble()

        tolerance = self.TESSELLATION_QUALITY.get(tessellation, 0.1)
        cq.exporters.export(
            self._assembly,
            output_path,
            exportType="STL",
            tolerance=tolerance,
        )
        logger.info(f"Exported STL: {output_path} (tessellation={tessellation})")
        return output_path

    def export_glb(
        self,
        output_path: str,
        tessellation: str = "high",
        postprocess: bool = True,
        subdivision_iterations: int = 1,
        target_faces: int = 50000,
    ) -> str:
        """Export assembly to GLB with post-processing.

        Pipeline: CadQuery → STL (high tessellation) → trimesh → post-process → GLB

        Args:
            output_path: Path for the output GLB file
            tessellation: STL tessellation quality
            postprocess: Whether to apply subdivision + decimation
            subdivision_iterations: Number of subdivision passes
            target_faces: Target face count after decimation

        Returns:
            Path to the exported GLB file
        """
        from ..postprocessing.mesh_postprocessor import stl_to_glb

        # Export to temporary STL first
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
            stl_path = tmp.name

        self.export_stl(stl_path, tessellation=tessellation)

        # Convert to GLB with post-processing
        glb_path = stl_to_glb(
            stl_path,
            output_path,
            postprocess=postprocess,
            subdivision_iterations=subdivision_iterations,
            target_faces=target_faces,
        )

        # Clean up temp STL
        try:
            Path(stl_path).unlink()
        except Exception:
            pass

        return glb_path

    def generate_components_separate(self) -> dict[str, cq.Workplane]:
        """Generate all components but keep them separate.

        Useful for multi-material printing or component-level export.

        Returns:
            Dict mapping component name to CadQuery Workplane
        """
        if self._socket is None:
            self.generate_socket()
        if self._forearm is None:
            self.generate_forearm()
        if self._hand is None:
            self.generate_hand()

        return {
            "socket": self._socket,
            "forearm": self._forearm,
            "hand": self._hand,
        }

    @property
    def assembly(self) -> Optional[cq.Workplane]:
        return self._assembly

    @property
    def socket(self) -> Optional[cq.Workplane]:
        return self._socket

    @property
    def forearm(self) -> Optional[cq.Workplane]:
        return self._forearm

    @property
    def hand(self) -> Optional[cq.Workplane]:
        return self._hand

