"""
Prosthetic Arm Generator — Unified Web API
=============================================
FastAPI backend serving measurement-driven arm generation + texture synthesis.
Serves the unified frontend SPA at root.
"""

import logging
import os
import uuid
import traceback
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, List

logger = logging.getLogger(__name__)

app = FastAPI(title="Prosthetic Arm Generator", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Output directory for generated files
OUTPUT_ROOT = Path(__file__).parent.parent.parent / "output" / "webapp"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

# Serve static frontend files
STATIC_DIR = Path(__file__).parent / "webapp"


class GenerationRequest(BaseModel):
    """Measurement inputs for arm generation."""
    residual_limb_length: float = Field(180.0, ge=30, le=500)
    circumference_proximal: float = Field(280.0, ge=100, le=600)
    circumference_distal: float = Field(160.0, ge=20, le=350)
    taper_exponent: float = Field(1.2, ge=0.5, le=3.0)
    eccentricity: float = Field(0.1, ge=0.0, le=0.15)

    wall_thickness: float = Field(4.0, ge=2.0, le=10.0)
    forearm_length: float = Field(250.0, ge=100, le=400)
    palm_width: float = Field(85.0, ge=50, le=130)
    palm_length: float = Field(100.0, ge=60, le=150)
    finger_length: float = Field(80.0, ge=40, le=120)
    grip_angle: float = Field(15.0, ge=0, le=80)
    thumb_angle: float = Field(45.0, ge=20, le=70)

    generate_socket: bool = True
    generate_forearm: bool = True
    generate_hand: bool = True

    apply_texture: bool = False
    material_preset: str = "skin"
    skin_tone: str = "medium"


class TextureRequest(BaseModel):
    """Apply texture to an existing job."""
    job_id: str
    material_preset: str = "skin"
    skin_tone: str = "medium"


class GenerationResponse(BaseModel):
    job_id: str
    status: str
    message: str
    files: dict[str, str] = {}
    stats: dict = {}
    textured: bool = False


@app.get("/")
async def index():
    """Serve the unified frontend."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Prosthetic Arm Generator API. Frontend not found at " + str(STATIC_DIR)}


@app.post("/api/generate", response_model=GenerationResponse)
async def generate_arm(req: GenerationRequest):
    """Generate a prosthetic arm from measurements."""
    try:
        from prosthetic_gen.measurement_input.schema import create_synthetic_measurements
        from prosthetic_gen.parametric_engine.constraints import SocketConstraints
        from prosthetic_gen.parametric_engine.assembler import ProstheticAssembler
        from prosthetic_gen.parametric_engine.exporter import MeshExporter
        import cadquery as cq
        import trimesh
        import numpy as np

        job_id = str(uuid.uuid4())[:8]
        job_dir = OUTPUT_ROOT / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Create measurements
        measurements = create_synthetic_measurements(
            limb_length=req.residual_limb_length,
            proximal_circ=req.circumference_proximal,
            distal_circ=req.circumference_distal,
            taper_exponent=req.taper_exponent,
            eccentricity=req.eccentricity,
        )

        # Configure constraints
        constraints = SocketConstraints(
            nominal_wall_thickness=req.wall_thickness,
            forearm_length=req.forearm_length,
            palm_width=req.palm_width,
            palm_length=req.palm_length,
            middle_finger_length=req.finger_length,
            grip_angle_deg=req.grip_angle,
            thumb_angle_deg=req.thumb_angle,
        )

        # Generate assembly
        assembler = ProstheticAssembler(measurements, constraints)

        components = []
        component_names = []

        if req.generate_socket:
            assembler.generate_socket()
            components.append(assembler.socket)
            component_names.append("socket")

        if req.generate_forearm:
            assembler.generate_forearm()
            components.append(assembler.forearm)
            component_names.append("forearm")

        if req.generate_hand:
            if not req.generate_forearm:
                assembler.generate_forearm()
            assembler.generate_hand()
            components.append(assembler.hand)
            component_names.append("hand")

        if not components:
            raise HTTPException(status_code=400, detail="Select at least one component")

        # Union selected components
        assembly = components[0]
        for comp in components[1:]:
            assembly = assembly.union(comp)

        # Export assembly
        exporter = MeshExporter(output_dir=str(job_dir))
        paths = exporter.export_all(assembly, base_name="prosthetic_arm")

        files = {}
        for fmt, path in paths.items():
            filename = os.path.basename(path)
            files[fmt] = f"/api/download/{job_id}/{filename}"

        # Fix normals on the GLB
        glb_path = paths.get("glb")
        if glb_path:
            mesh = trimesh.load(glb_path)
            if isinstance(mesh, trimesh.Scene):
                mesh = trimesh.util.concatenate(mesh.dump())
            mesh.fix_normals()
            mesh.visual.face_colors = np.tile([230, 200, 180, 255], (len(mesh.faces), 1))
            mesh.export(glb_path, file_type="glb")

        # Export individual components as GLB
        for comp, name in zip(components, component_names):
            comp_stl = str(job_dir / f"{name}.stl")
            cq.exporters.export(comp, comp_stl, exportType="STL", tolerance=0.05)
            comp_mesh = trimesh.load(comp_stl)
            if isinstance(comp_mesh, trimesh.Scene):
                comp_mesh = trimesh.util.concatenate(comp_mesh.dump())
            comp_mesh.fix_normals()
            comp_mesh.visual.face_colors = np.tile([230, 200, 180, 255], (len(comp_mesh.faces), 1))
            comp_glb = str(job_dir / f"{name}.glb")
            comp_mesh.export(comp_glb, file_type="glb")
            files[f"{name}_glb"] = f"/api/download/{job_id}/{name}.glb"

        # Get mesh stats
        stl_path = paths.get("stl")
        stats = {}
        if stl_path:
            mesh_stats = exporter.get_mesh_stats(stl_path)
            stats = {
                "vertices": mesh_stats.get("vertices", 0),
                "faces": mesh_stats.get("faces", 0),
                "watertight": mesh_stats.get("is_watertight", False),
                "volume_mm3": mesh_stats.get("volume_mm3"),
                "surface_area_mm2": mesh_stats.get("surface_area_mm2"),
                "bounding_box": mesh_stats.get("bounding_box"),
                "file_size_mb": round(os.path.getsize(stl_path) / (1024 * 1024), 2),
                "components": component_names,
            }

        # Apply texture if requested
        textured = False
        if req.apply_texture and glb_path:
            try:
                textured = _apply_texture(
                    job_dir, glb_path, req.material_preset, req.skin_tone, files
                )
            except Exception as tex_err:
                logger.warning(f"Texture synthesis failed: {tex_err}")

        return GenerationResponse(
            job_id=job_id,
            status="success",
            message=f"Generated {len(component_names)} components ({stats.get('faces', 0)} faces).",
            files=files,
            stats=stats,
            textured=textured,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generation failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/texture")
async def apply_texture_endpoint(req: TextureRequest):
    """Apply texture to an existing generated model."""
    job_dir = OUTPUT_ROOT / req.job_id
    glb_path = str(job_dir / "prosthetic_arm.glb")

    if not os.path.exists(glb_path):
        raise HTTPException(status_code=404, detail="Model not found. Generate first.")

    try:
        files = {}
        textured = _apply_texture(
            job_dir, glb_path, req.material_preset, req.skin_tone, files
        )
        return {
            "status": "success",
            "textured": textured,
            "files": files,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _apply_texture(job_dir, glb_path, material_preset, skin_tone, files):
    """Apply texture to a GLB file. Updates the files dict."""
    from prosthetic_gen.texture_synthesis.texturizer import Texturizer

    texturizer = Texturizer()
    textured_path = str(job_dir / f"prosthetic_arm_{material_preset}.glb")
    texturizer.apply(
        mesh_path=glb_path,
        material=material_preset,
        skin_tone=skin_tone,
        output_path=textured_path,
    )
    job_id = job_dir.name
    files[f"glb_{material_preset}"] = f"/api/download/{job_id}/prosthetic_arm_{material_preset}.glb"
    return True


@app.get("/api/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    """Download a generated file."""
    filepath = OUTPUT_ROOT / job_id / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    media_types = {
        ".stl": "application/sla",
        ".step": "application/step",
        ".glb": "model/gltf-binary",
    }
    ext = filepath.suffix.lower()
    media_type = media_types.get(ext, "application/octet-stream")

    return FileResponse(
        str(filepath),
        media_type=media_type,
        filename=filename,
    )


@app.get("/api/jobs")
async def list_jobs():
    """List recent generation jobs."""
    jobs = []
    if OUTPUT_ROOT.exists():
        for d in sorted(OUTPUT_ROOT.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
            if d.is_dir():
                files = [f.name for f in d.iterdir() if f.is_file()]
                jobs.append({
                    "job_id": d.name,
                    "files": files,
                    "created": d.stat().st_mtime,
                })
    return {"jobs": jobs}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
