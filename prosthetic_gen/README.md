# Prosthetic Socket Generator

**Measurement-driven, parametric framework for rapid prosthetic arm generation.**

Given sparse anthropometric measurements, this system automatically generates a watertight prosthetic socket model within minutes using deterministic CadQuery parametric geometry.

## Architecture

- **Parametric Core**: CadQuery-based elliptical profile lofting with anatomical, mechanical, and fabrication constraints
- **Texture Synthesis** (Phase 3): Hunyuan3D-Paint for realistic cosmetic textures — excluded from geometry generation
- **Validation**: Cross-section deviation ≤1mm, watertightness, wall thickness, deterministic replay

## Quick Start

```bash
# Install dependencies
pip install cadquery pydantic trimesh numpy gradio

# Run demo
python -m prosthetic_gen.demo

# Run tests
pytest prosthetic_gen/tests/

# Launch UI
python -m prosthetic_gen.interface.gradio_app
```

## Measurement Schema

| Input | Unit |
|-------|------|
| Residual limb length | mm |
| Circumference at 0/25/50/75/100% | mm |
| Major/minor diameter at 0/50/100% | mm |
| Load-sensitive zones | flags |

## Output Formats

- **STEP** — parametric CAD (clinical editing)
- **STL** — 3D printing / fabrication
- **GLB** — web preview / Hunyuan3D-Paint input

## Project Structure

```
prosthetic_gen/
├── measurement_input/     # Schema, validation, normalization
├── parametric_engine/     # CadQuery profiles, lofting, constraints, export
├── texture_synthesis/     # Hunyuan3D-Paint wrapper (Phase 3)
├── postprocessing/        # Dimensional validation
├── interface/             # Gradio UI, FastAPI
├── tests/                 # pytest suite
└── demo.py                # End-to-end demo
```

## License

Research use only. Hunyuan3D-2 components under Tencent Hunyuan Non-Commercial License.
