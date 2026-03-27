# 🦾 Prosthetic Arm Generator

**Automatically design a custom prosthetic arm from patient measurements — no CAD expertise needed.**

A measurement-driven, parametric pipeline that takes clinical limb dimensions and generates a complete, 3D-printable transradial (below-elbow) prosthetic arm — including socket, forearm tube, and articulated hand — with a web-based interface for configuration, 3D preview, texture application, and file export.

---

## ✨ Features

- **Measurement-Driven Design** — Enter patient limb measurements, get a custom-fitted prosthetic arm in seconds
- **Full Arm Assembly** — Socket + forearm tube + articulated hand (palm, 4 fingers, thumb)
- **Anatomically Informed** — Elliptical cross-sections, ulnar ridge, dorsal palm arch, thenar eminence, joint widening
- **Web Application** — Browser-based UI with interactive 3D viewer (Three.js + OrbitControls)
- **Multiple Textures** — Skin tone (light/medium/dark), metallic, plastic, carbon fiber
- **Export Formats** — STL (3D printing), STEP (CAD editing), GLB (web preview)
- **Deterministic** — Same inputs always produce identical geometry

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- pip

### Installation

```bash
# Clone the repo
git clone https://github.com/kishor78945/prosthetic-arm-generator.git
cd prosthetic-arm-generator

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install cadquery pydantic trimesh numpy fastapi uvicorn pillow
```

### Run the Web App

```bash
python -m uvicorn prosthetic_gen.interface.api:app --port 8000
```

Open **http://localhost:8000** in your browser.

### Quick Test (No Web App)

```bash
python diagnose_geometry.py
```

Generates individual STL components in `output/phase4_visual/`.

---

## 🖥️ Web Application

The unified single-page app has **4 tabs**:

| Tab | Description |
|-----|-------------|
| **Measurements** | Input form with sliders for limb dimensions, constraints, and component toggles |
| **3D Preview** | Interactive Three.js viewer — rotate, zoom, wireframe, per-component viewing |
| **Textures** | Material preset cards (skin/metallic/plastic/carbon fiber) + skin tone selector |
| **Export** | Download STL, STEP, GLB files (untextured + textured) |

---

## 📐 How It Works

```
Patient Measurements → Validation → CadQuery CAD Generation → Mesh Post-Processing → Texture → Export
```

### Pipeline Phases

**Phase 1 — Measurement Input**
- Limb length, circumferences at 5 stations, elliptical diameters
- Z-score outlier detection, taper monotonicity checks

**Phase 2 — Parametric Geometry Engine**
- **Socket**: Lofted elliptical shell from patient measurements with wall relief
- **Forearm**: 5-station elliptical loft (1.25:1 width:depth), S-curve taper, ulnar ridge
- **Hand**: Palm with dorsal arch, thenar eminence, 4 fingers (3 phalanges each), thumb

**Phase 3 — Post-Processing & Textures**
- Subdivision smoothing, normal recalculation, decimation
- Procedural PBR textures: skin, metallic, plastic, carbon fiber

**Phase 4 — Export**
- STL (3D printing), STEP (CAD editing), GLB (web preview)

---

## 📁 Project Structure

```
prosthetic-arm-generator/
├── prosthetic_gen/                    # Main package
│   ├── measurement_input/
│   │   ├── schema.py                 # Pydantic data model (StumpMeasurements)
│   │   └── normalizer.py             # Outlier detection & validation
│   ├── parametric_engine/
│   │   ├── constraints.py            # Design parameters & limits
│   │   ├── profile_generator.py      # Elliptical cross-section profiles
│   │   ├── socket_generator.py       # Patient-fitted socket shell
│   │   ├── forearm_generator.py      # Hollow forearm tube + ulnar ridge
│   │   ├── hand_generator.py         # Palm, fingers, thumb with thenar pad
│   │   ├── assembler.py              # Component assembly & union
│   │   └── exporter.py               # STL / STEP / GLB export
│   ├── postprocessing/
│   │   ├── mesh_postprocessor.py     # Subdivision, normals, decimation
│   │   └── validator.py              # Wall thickness & watertight checks
│   ├── texture_synthesis/
│   │   └── texturizer.py             # Material texture application
│   ├── interface/
│   │   ├── api.py                    # FastAPI backend (REST API)
│   │   ├── gradio_app.py             # Alternative Gradio UI
│   │   └── webapp/index.html         # Unified SPA frontend
│   └── tests/                        # pytest test suite
├── diagnose_geometry.py              # Component-level testing
├── regenerate_arm.py                 # Full regeneration script
├── convert_to_glb.py                 # STL → GLB conversion
├── PROJECT_SUMMARY.txt               # Detailed project summary
└── .gitignore
```

---

## 🔧 Measurement Schema

| Input | Unit | Range |
|-------|------|-------|
| Residual limb length | mm | 30–500 |
| Circumferences (5 stations) | mm | 20–600 |
| Elliptical diameters (3 stations) | mm | auto |
| Load-sensitive zones | flags | olecranon, epicondyles, etc. |
| Wall thickness | mm | 2–10 |
| Forearm length | mm | 100–400 |
| Palm width / length | mm | 50–150 |
| Finger length | mm | 40–120 |
| Grip angle | deg | 0–80 |
| Thumb abduction | deg | 20–70 |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| CAD Engine | CadQuery |
| Mesh Processing | trimesh |
| Backend | FastAPI + Uvicorn |
| Frontend | Vanilla HTML/CSS/JS |
| 3D Viewer | Three.js |
| Validation | Pydantic |
| Textures | Pillow (PIL) |
| Math | NumPy |

---

## 📋 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serve web application |
| `POST` | `/api/generate` | Generate prosthetic arm from measurements |
| `POST` | `/api/texture` | Apply texture to existing model |
| `GET` | `/api/download/{job_id}/{file}` | Download generated file |
| `GET` | `/api/jobs` | List recent generation jobs |

---

## ⚠️ Limitations

- This is a **design visualization tool**, not a structurally validated prosthetic
- Textures are procedural, not AI-generated photorealistic
- Hand is a simplified anatomical proxy — no functional grip mechanism
- Currently supports **transradial (below-elbow)** amputation only

---

## 📄 License

Research and educational use only.
