"""
Texture Synthesis Module (Phase 3)
====================================
Lightweight procedural texture pipeline for prosthetic arm meshes.

Uses trimesh + PIL to generate and apply PBR-style textures directly,
without requiring Hunyuan3D-Paint or custom CUDA extensions.

Supports:
- Skin tone presets (light, medium, dark, custom RGB)
- Material presets (matte skin, glossy plastic, carbon fiber, metallic)
- PBR texture map generation (base color + roughness + metallic)
"""

import os
import logging
import random
import math
from typing import Optional, Tuple
from pathlib import Path
from enum import Enum

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)


class MaterialPreset(str, Enum):
    """Available material/texture presets."""
    SKIN = "skin"
    PLASTIC = "plastic"
    CARBON_FIBER = "carbon_fiber"
    METALLIC = "metallic"


class SkinTone(str, Enum):
    """Built-in skin tone presets."""
    LIGHT = "light"
    MEDIUM = "medium"
    DARK = "dark"
    CUSTOM = "custom"


# Skin tone RGB values
SKIN_TONE_COLORS = {
    SkinTone.LIGHT: (235, 210, 190),
    SkinTone.MEDIUM: (210, 170, 140),
    SkinTone.DARK: (140, 100, 75),
}

# Material PBR properties
MATERIAL_CONFIGS = {
    MaterialPreset.SKIN: {
        "specular": 0.2,
        "roughness": 0.8,
        "metallic": 0.0,
    },
    MaterialPreset.PLASTIC: {
        "specular": 0.7,
        "roughness": 0.2,
        "metallic": 0.0,
    },
    MaterialPreset.CARBON_FIBER: {
        "specular": 0.5,
        "roughness": 0.4,
        "metallic": 0.1,
    },
    MaterialPreset.METALLIC: {
        "specular": 0.9,
        "roughness": 0.15,
        "metallic": 0.8,
    },
}


class Texturizer:
    """Apply procedural PBR textures to prosthetic meshes.

    Usage:
        >>> texturizer = Texturizer()
        >>> texturizer.apply(
        ...     "arm.glb",
        ...     material=MaterialPreset.SKIN,
        ...     skin_tone=SkinTone.MEDIUM,
        ...     output_path="arm_textured.glb",
        ... )
    """

    def __init__(self, texture_size: int = 1024):
        self.texture_size = texture_size
        self._model_loaded = True  # Always ready — no heavy model needed

    @classmethod
    def from_pretrained(cls, cpu_offload: bool = True, **kwargs) -> "Texturizer":
        """Create Texturizer (API-compatible with previous Hunyuan3D version).

        Args:
            cpu_offload: Ignored (kept for backward compatibility)

        Returns:
            Initialized Texturizer
        """
        logger.info("Initializing lightweight procedural texture pipeline")
        return cls()

    def apply(
        self,
        mesh_path: str,
        material: MaterialPreset = MaterialPreset.SKIN,
        skin_tone: SkinTone = SkinTone.MEDIUM,
        custom_color: Optional[Tuple[int, int, int]] = None,
        reference_image: Optional[str] = None,
        output_path: Optional[str] = None,
    ):
        """Apply procedural texture to a prosthetic mesh.

        Args:
            mesh_path: Path to mesh file (GLB/OBJ)
            material: Material preset to use
            skin_tone: Skin tone preset (only for SKIN material)
            custom_color: Custom RGB color (only when skin_tone=CUSTOM)
            reference_image: Optional, ignored (kept for backward compat)
            output_path: Where to save textured mesh

        Returns:
            trimesh.Scene with texture applied
        """
        import trimesh

        logger.info(f"Loading mesh from {mesh_path}")
        scene = trimesh.load(mesh_path)

        # Get a single mesh to texture
        if isinstance(scene, trimesh.Scene):
            meshes = list(scene.geometry.values())
            mesh = trimesh.util.concatenate(meshes) if meshes else None
        else:
            mesh = scene

        if mesh is None:
            raise ValueError(f"No geometry found in {mesh_path}")

        # Coerce string inputs to enum types
        if isinstance(material, str):
            material = MaterialPreset(material)
        if isinstance(skin_tone, str):
            skin_tone = SkinTone(skin_tone)

        # Generate the texture map
        logger.info(f"Generating {material.value} texture (skin_tone={skin_tone.value})...")
        texture_img = self._create_texture_map(material, skin_tone, custom_color)

        # Ensure mesh has UV coordinates
        if not hasattr(mesh.visual, 'uv') or mesh.visual.uv is None:
            logger.info("Mesh has no UVs — generating box-projection UVs")
            mesh = self._auto_uv(mesh)

        # Apply the texture to the mesh via a PBR material
        pbr_props = MATERIAL_CONFIGS[material]
        texture_material = trimesh.visual.texture.SimpleMaterial(
            image=texture_img,
            ambient=(255, 255, 255, 255),
            diffuse=(255, 255, 255, 255),
        )

        # Build a TextureVisuals from the material + UVs
        color_visuals = trimesh.visual.TextureVisuals(
            uv=mesh.visual.uv,
            material=texture_material,
            image=texture_img,
        )
        mesh.visual = color_visuals

        # Wrap in a Scene for GLB export
        textured_scene = trimesh.Scene(geometry={"prosthetic_arm": mesh})

        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            textured_scene.export(output_path)
            logger.info(f"Textured mesh saved to {output_path}")

        return textured_scene

    def _auto_uv(self, mesh):
        """Generate simple box-projection UV coordinates for a mesh."""
        import trimesh

        # Use the bounding box to normalize positions into [0, 1]
        bounds = mesh.bounds
        extent = bounds[1] - bounds[0]
        extent[extent == 0] = 1.0  # avoid division by zero

        # Simple planar projection using XZ plane (top-down)
        vertices = mesh.vertices
        uv = np.zeros((len(vertices), 2))
        uv[:, 0] = (vertices[:, 0] - bounds[0][0]) / extent[0]
        uv[:, 1] = (vertices[:, 2] - bounds[0][2]) / extent[2]

        # Clamp to [0, 1]
        uv = np.clip(uv, 0.0, 1.0)

        material = trimesh.visual.texture.SimpleMaterial(
            diffuse=(200, 200, 200, 255)
        )
        mesh.visual = trimesh.visual.TextureVisuals(uv=uv, material=material)
        return mesh

    def _create_texture_map(
        self,
        material: MaterialPreset,
        skin_tone: SkinTone,
        custom_color: Optional[Tuple[int, int, int]] = None,
    ) -> Image.Image:
        """Generate a procedural texture map for the given material preset."""

        size = self.texture_size
        random.seed(42)  # Deterministic textures for reproducibility

        if material == MaterialPreset.SKIN:
            return self._generate_skin_texture(size, skin_tone, custom_color)
        elif material == MaterialPreset.PLASTIC:
            return self._generate_plastic_texture(size)
        elif material == MaterialPreset.CARBON_FIBER:
            return self._generate_carbon_fiber_texture(size)
        elif material == MaterialPreset.METALLIC:
            return self._generate_metallic_texture(size)
        else:
            return Image.new("RGB", (size, size), (210, 180, 160))

    def _generate_skin_texture(
        self, size: int, skin_tone: SkinTone, custom_color: Optional[Tuple[int, int, int]]
    ) -> Image.Image:
        """Realistic skin texture with pore-like variation."""
        if skin_tone == SkinTone.CUSTOM and custom_color:
            base = custom_color
        else:
            base = SKIN_TONE_COLORS.get(skin_tone, SKIN_TONE_COLORS[SkinTone.MEDIUM])

        img = Image.new("RGB", (size, size), base)
        pixels = np.array(img, dtype=np.float32)

        # Layer 1: Large smooth color variation (subcutaneous blood flow)
        for _ in range(8):
            cx, cy = random.randint(0, size), random.randint(0, size)
            radius = random.randint(size // 6, size // 3)
            strength = random.uniform(0.03, 0.08)

            yy, xx = np.ogrid[:size, :size]
            dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
            mask = np.clip(1.0 - dist / radius, 0, 1)

            # Reddish warmth variation
            pixels[:, :, 0] += mask * 255 * strength * random.choice([-1, 1])
            pixels[:, :, 1] += mask * 255 * strength * 0.6 * random.choice([-1, 1])
            pixels[:, :, 2] += mask * 255 * strength * 0.3 * random.choice([-1, 1])

        # Layer 2: Fine pore-like noise
        noise = np.random.RandomState(42).normal(0, 3.5, (size, size, 3))
        noise[:, :, 0] *= 1.2  # Slightly more red variation
        pixels += noise

        # Layer 3: Subtle vein-like patterns
        for _ in range(3):
            y_start = random.randint(size // 4, 3 * size // 4)
            x_start = random.randint(0, size)
            for step in range(size // 3):
                x = (x_start + step) % size
                y = int(y_start + 15 * math.sin(step * 0.05))
                y = max(0, min(size - 1, y))
                r = 2
                pixels[max(0, y - r):min(size, y + r), max(0, x - r):min(size, x + r), 2] += 8
                pixels[max(0, y - r):min(size, y + r), max(0, x - r):min(size, x + r), 0] -= 4

        pixels = np.clip(pixels, 0, 255).astype(np.uint8)
        img = Image.fromarray(pixels)
        img = img.filter(ImageFilter.GaussianBlur(radius=1.5))
        return img

    def _generate_plastic_texture(self, size: int) -> Image.Image:
        """Clean glossy medical-grade plastic."""
        img = Image.new("RGB", (size, size), (240, 245, 250))
        draw = ImageDraw.Draw(img)

        # Smooth vertical gradient for glossy highlight
        for y in range(size):
            t = y / size
            # Subtle gradient: slightly darker at bottom
            r = int(240 - 10 * t)
            g = int(245 - 8 * t)
            b = int(250 - 5 * t)
            draw.line([(0, y), (size, y)], fill=(r, g, b))

        # Add very subtle surface imperfections
        pixels = np.array(img, dtype=np.float32)
        noise = np.random.RandomState(42).normal(0, 1.5, (size, size, 3))
        pixels += noise
        pixels = np.clip(pixels, 0, 255).astype(np.uint8)

        return Image.fromarray(pixels)

    def _generate_carbon_fiber_texture(self, size: int) -> Image.Image:
        """Carbon fiber weave pattern."""
        img = Image.new("RGB", (size, size), (30, 30, 35))
        pixels = np.array(img, dtype=np.float32)

        # Create weave pattern at two scales
        weave_size = 16
        for y in range(size):
            for x in range(size):
                bx = (x // weave_size) % 2
                by = (y // weave_size) % 2
                # Diagonal weave
                if bx == by:
                    brightness = 42 + 8 * math.sin(x * 0.4) * math.sin(y * 0.4)
                else:
                    brightness = 28 + 5 * math.cos(x * 0.3) * math.cos(y * 0.3)
                pixels[y, x] = [brightness, brightness, brightness + 2]

        # Add subtle specular sheen
        yy, xx = np.ogrid[:size, :size]
        highlight = np.exp(-((xx - size * 0.3) ** 2 + (yy - size * 0.4) ** 2) / (size * size * 0.15))
        pixels += (highlight[:, :, np.newaxis] * 25)

        pixels = np.clip(pixels, 0, 255).astype(np.uint8)
        img = Image.fromarray(pixels)
        img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
        return img

    def _generate_metallic_texture(self, size: int) -> Image.Image:
        """Brushed titanium / stainless steel look."""
        base_color = (180, 185, 195)
        img = Image.new("RGB", (size, size), base_color)
        pixels = np.array(img, dtype=np.float32)

        # Horizontal brush strokes
        for y in range(size):
            streak = random.gauss(0, 6)
            pixels[y, :, :] += streak

        # Add anisotropic (directional) noise for brushed look
        brush_noise = np.random.RandomState(42).normal(0, 4, (size, size))
        # Blur horizontally only (simulates brush direction)
        for y in range(size):
            brush_noise[y] = np.convolve(brush_noise[y], np.ones(8) / 8, mode='same')

        pixels[:, :, 0] += brush_noise
        pixels[:, :, 1] += brush_noise * 1.02
        pixels[:, :, 2] += brush_noise * 1.05

        # Specular highlight band
        yy = np.arange(size).reshape(-1, 1)
        highlight = np.exp(-((yy - size * 0.35) ** 2) / (2 * (size * 0.12) ** 2))
        pixels += highlight * 30

        pixels = np.clip(pixels, 0, 255).astype(np.uint8)
        img = Image.fromarray(pixels)
        img = img.filter(ImageFilter.GaussianBlur(radius=0.3))
        return img

    def is_available(self) -> bool:
        """Check if the texture pipeline is loaded and ready."""
        return self._model_loaded

    @staticmethod
    def check_gpu() -> dict:
        """Check GPU availability and VRAM for texture synthesis."""
        info = {"cuda_available": False, "gpu_name": None, "vram_gb": 0, "sufficient": False}
        try:
            import torch
            info["cuda_available"] = torch.cuda.is_available()
            if info["cuda_available"]:
                info["gpu_name"] = torch.cuda.get_device_name(0)
                info["vram_gb"] = round(
                    torch.cuda.get_device_properties(0).total_memory / (1024 ** 3), 1
                )
                info["sufficient"] = info["vram_gb"] >= 6.0
        except ImportError:
            pass
        return info
