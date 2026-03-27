"""
Prosthetic Socket Generator — Gradio Interface
=================================================
Web UI for prosthetists to input measurements, preview sockets, and export.
"""

import os
import tempfile
import time

import gradio as gr

from ..measurement_input.schema import StumpMeasurements, LoadZone, create_synthetic_measurements
from ..measurement_input.normalizer import MeasurementNormalizer
from ..parametric_engine.constraints import SocketConstraints


def generate_socket(
    limb_length, circ_0, circ_25, circ_50, circ_75, circ_100,
    major_d_0, minor_d_0, major_d_50, minor_d_50, major_d_100, minor_d_100,
    wall_thickness, liner_thickness, distal_cap_type,
    load_olecranon, load_medial, load_lateral, load_bicipital, load_distal,
):
    """Generate socket from form inputs."""
    try:
        # Build load zones
        load_zones = 0
        if load_olecranon:
            load_zones |= LoadZone.OLECRANON.value
        if load_medial:
            load_zones |= LoadZone.MEDIAL_EPICONDYLE.value
        if load_lateral:
            load_zones |= LoadZone.LATERAL_EPICONDYLE.value
        if load_bicipital:
            load_zones |= LoadZone.BICIPITAL_TENDON.value
        if load_distal:
            load_zones |= LoadZone.DISTAL_END.value

        measurements = StumpMeasurements(
            residual_limb_length=limb_length,
            circumference_0=circ_0, circumference_25=circ_25,
            circumference_50=circ_50, circumference_75=circ_75,
            circumference_100=circ_100,
            major_diameter_0=major_d_0, minor_diameter_0=minor_d_0,
            major_diameter_50=major_d_50, minor_diameter_50=minor_d_50,
            major_diameter_100=major_d_100, minor_diameter_100=minor_d_100,
            load_zones=load_zones,
        )

        # Validate
        normalizer = MeasurementNormalizer()
        report = normalizer.validate(measurements)

        # Configure constraints
        constraints = SocketConstraints(
            nominal_wall_thickness=wall_thickness,
            liner_thickness=liner_thickness,
            total_interface_gap=1.5 + liner_thickness,
            distal_cap_type=distal_cap_type,
        )

        # Generate
        try:
            import cadquery as cq
            from ..parametric_engine.socket_generator import SocketGenerator
            from ..parametric_engine.exporter import MeshExporter

            start = time.time()
            gen = SocketGenerator(measurements, constraints)
            result = gen.generate_simple()
            elapsed = time.time() - start

            # Export
            output_dir = tempfile.mkdtemp(prefix="prosthetic_output_")
            exporter = MeshExporter(output_dir=output_dir)
            paths = exporter.export_all(result, base_name="socket")

            # Validate
            from ..postprocessing.validator import SocketValidator
            validator = SocketValidator(measurements, constraints)
            validation = validator.validate_mesh(paths["stl"])

            status = f"✅ Generated in {elapsed:.2f}s\n\n"
            status += f"Validation:\n{validation.summary()}\n\n"
            status += f"Measurement Check:\n{report}\n\n"
            status += f"Files:\n"
            for fmt, path in paths.items():
                size_kb = os.path.getsize(path) / 1024
                status += f"  {fmt.upper()}: {size_kb:.1f} KB\n"

            return paths.get("glb"), paths.get("stl"), paths.get("step"), status

        except ImportError:
            return None, None, None, f"❌ CadQuery not installed\n\nMeasurement check:\n{report}"

    except Exception as e:
        return None, None, None, f"❌ Error: {str(e)}"


def load_synthetic():
    """Load synthetic measurements into the form."""
    m = create_synthetic_measurements()
    return (
        m.residual_limb_length, m.circumference_0, m.circumference_25,
        m.circumference_50, m.circumference_75, m.circumference_100,
        m.major_diameter_0, m.minor_diameter_0,
        m.major_diameter_50, m.minor_diameter_50,
        m.major_diameter_100, m.minor_diameter_100,
    )


def create_gradio_app() -> gr.Blocks:
    """Build and return the Gradio app."""
    with gr.Blocks(
        title="Prosthetic Socket Generator",
        theme=gr.themes.Soft(),
    ) as app:
        gr.Markdown("# 🦾 Parametric Prosthetic Socket Generator")
        gr.Markdown("Input patient measurements to generate a clinically editable prosthetic socket.")

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Measurements (mm)")

                limb_length = gr.Number(label="Residual Limb Length", value=180.0)

                gr.Markdown("**Circumferences**")
                circ_0 = gr.Number(label="0% (Proximal)", value=280.0)
                circ_25 = gr.Number(label="25%", value=260.0)
                circ_50 = gr.Number(label="50% (Midpoint)", value=240.0)
                circ_75 = gr.Number(label="75%", value=210.0)
                circ_100 = gr.Number(label="100% (Distal)", value=160.0)

                gr.Markdown("**Elliptical Diameters**")
                with gr.Row():
                    major_d_0 = gr.Number(label="Major Ø 0%", value=95.0)
                    minor_d_0 = gr.Number(label="Minor Ø 0%", value=85.0)
                with gr.Row():
                    major_d_50 = gr.Number(label="Major Ø 50%", value=80.0)
                    minor_d_50 = gr.Number(label="Minor Ø 50%", value=72.0)
                with gr.Row():
                    major_d_100 = gr.Number(label="Major Ø 100%", value=55.0)
                    minor_d_100 = gr.Number(label="Minor Ø 100%", value=48.0)

            with gr.Column(scale=1):
                gr.Markdown("### Constraints")
                wall_thickness = gr.Slider(2.0, 8.0, value=4.0, step=0.5, label="Wall Thickness (mm)")
                liner_thickness = gr.Slider(1.0, 6.0, value=3.0, step=0.5, label="Liner Thickness (mm)")
                distal_cap_type = gr.Dropdown(
                    ["rounded", "flat", "open"],
                    value="rounded",
                    label="Distal Cap Type",
                )

                gr.Markdown("### Load-Sensitive Zones")
                load_olecranon = gr.Checkbox(label="Olecranon", value=True)
                load_medial = gr.Checkbox(label="Medial Epicondyle")
                load_lateral = gr.Checkbox(label="Lateral Epicondyle")
                load_bicipital = gr.Checkbox(label="Bicipital Tendon")
                load_distal = gr.Checkbox(label="Distal End", value=True)

                with gr.Row():
                    gen_btn = gr.Button("🔨 Generate Socket", variant="primary", size="lg")
                    load_btn = gr.Button("📋 Load Synthetic Data", size="lg")

        with gr.Row():
            model_viewer = gr.Model3D(label="3D Preview")
            with gr.Column():
                status_box = gr.Textbox(label="Status / Validation", lines=15, interactive=False)
                stl_file = gr.File(label="Download STL")
                step_file = gr.File(label="Download STEP")

        gen_btn.click(
            fn=generate_socket,
            inputs=[
                limb_length, circ_0, circ_25, circ_50, circ_75, circ_100,
                major_d_0, minor_d_0, major_d_50, minor_d_50, major_d_100, minor_d_100,
                wall_thickness, liner_thickness, distal_cap_type,
                load_olecranon, load_medial, load_lateral, load_bicipital, load_distal,
            ],
            outputs=[model_viewer, stl_file, step_file, status_box],
        )

        load_btn.click(
            fn=load_synthetic,
            outputs=[
                limb_length, circ_0, circ_25, circ_50, circ_75, circ_100,
                major_d_0, minor_d_0, major_d_50, minor_d_50, major_d_100, minor_d_100,
            ],
        )

    return app


if __name__ == "__main__":
    app = create_gradio_app()
    app.launch(server_name="0.0.0.0", server_port=7860)
