"""
Articulated Hand Generator
=============================
CadQuery-based parametric hand with anatomical palm, 5 fingers, and thumb.
Simplified anatomical proxy for full-arm visualization.

The thumb uses a thenar eminence (pad of flesh) that bridges it to
the palm body, ensuring a single, connected solid.
"""

import math
from typing import Optional

import cadquery as cq

from .constraints import SocketConstraints


class HandGenerator:
    """Generates a parametric prosthetic hand with anatomical geometry.

    Key design features:
    - Palm: Lofted elliptical cross-sections (wider at knuckles, tapered at wrist)
    - Dorsal arch: Palm top is convex, bottom is flatter
    - Thenar eminence: Fleshy pad connecting thumb base to palm
    - Fingers: 3-phalanx segments with interphalangeal joint widening
    - Thumb: 2-segment, originates INSIDE the palm with thenar bridge

    This is a simplified anatomical proxy for visualization,
    not a functional hand design. All dimensions are parametric.
    """

    FINGER_NAMES = ["index", "middle", "ring", "pinky"]

    def __init__(
        self,
        constraints: Optional[SocketConstraints] = None,
        wrist_z: float = 0.0,
    ):
        self.constraints = constraints or SocketConstraints()
        self.wrist_z = wrist_z
        self._result: Optional[cq.Workplane] = None

    # ----------------------------------------------------------------
    # Wrist connector
    # ----------------------------------------------------------------
    def _build_wrist_connector(self) -> cq.Workplane:
        """Male wrist plug that inserts into forearm's female socket."""
        c = self.constraints
        plug_r = c.wrist_joint_diameter / 2 - c.wrist_joint_clearance
        plug_length = c.wrist_joint_length * 0.9

        connector = (
            cq.Workplane("XY")
            .workplane(offset=self.wrist_z)
            .circle(plug_r)
            .extrude(plug_length)
        )
        return connector

    # ----------------------------------------------------------------
    # Palm
    # ----------------------------------------------------------------
    def _build_palm(self) -> cq.Workplane:
        """Anatomical palm via lofted elliptical cross-sections.

        - Narrower at wrist (70%), full width at knuckles
        - Dorsal arch (convex top, flat bottom)
        - Smooth 5-station loft
        """
        c = self.constraints
        w = c.palm_width
        l = c.palm_length
        t = c.palm_thickness

        palm_z_start = self.wrist_z + c.wrist_joint_length * 0.9

        n_sections = 5
        sections = []
        for i in range(n_sections):
            frac = i / (n_sections - 1)
            z = palm_z_start + frac * l

            # Width: 70% at wrist → 100% at knuckles
            width_factor = 0.70 + 0.30 * frac
            sec_w = w * width_factor

            # Thickness: peaks at 40% along palm (bell curve)
            thickness_factor = 0.85 + 0.15 * math.exp(
                -0.5 * ((frac - 0.4) / 0.3) ** 2
            )
            sec_t = t * thickness_factor

            # Dorsal arch: offset Y+ for convex top, flat bottom
            dorsal_offset = t * 0.08 * math.sin(math.pi * frac)

            sections.append((z, sec_w / 2, sec_t / 2, dorsal_offset))

        # Build palm as single continuous loft
        palm_wp = cq.Workplane("XY")
        for i, (z, sa, sb, dy) in enumerate(sections):
            if i == 0:
                palm_wp = palm_wp.workplane(offset=z).center(0, dy).ellipse(sa, sb)
            else:
                dz = z - sections[i - 1][0]
                dy_delta = dy - sections[i - 1][3]
                palm_wp = palm_wp.workplane(offset=dz).center(0, dy_delta).ellipse(sa, sb)
        palm = palm_wp.loft(combine=True)

        return palm

    # ----------------------------------------------------------------
    # Thenar eminence (thumb mount pad)
    # ----------------------------------------------------------------
    def _build_thenar_eminence(self, palm_z: float) -> cq.Workplane:
        """Build a fleshy pad on the lateral side of the palm for thumb attachment.

        The thenar eminence is the muscular pad at the base of the thumb.
        We model it as an elongated ovoid shape that:
        - Starts flush with the palm's lateral (-X) surface
        - Extends slightly outward
        - Creates the attachment surface for the thumb

        This ensures the thumb is geometrically connected to the palm body.
        """
        c = self.constraints
        half_w = c.palm_width / 2

        # Thenar pad dimensions
        pad_length = c.palm_length * 0.45  # spans lower half of palm
        pad_width = c.palm_width * 0.18    # protrudes outward from palm
        pad_height = c.palm_thickness * 0.6

        # Center position: lateral side of palm, lower-mid region
        pad_z_center = palm_z + c.palm_length * 0.35
        pad_x_center = -half_w * 0.75  # starts inside the palm edge

        # Build as an elongated ellipsoid using lofted sections
        n = 5
        thenar_wp = cq.Workplane("XY")
        for i in range(n):
            frac = i / (n - 1)
            z = pad_z_center - pad_length / 2 + frac * pad_length

            # Elliptical cross-section that swells in the middle
            swell = math.sin(math.pi * frac)  # 0 → 1 → 0
            sx = pad_width * swell * 0.5 + 2.0  # at least 2mm radius
            sy = pad_height * swell * 0.5 + 2.0

            if i == 0:
                thenar_wp = thenar_wp.workplane(offset=z).center(pad_x_center, 0).ellipse(sx, sy)
            else:
                prev_z = pad_z_center - pad_length / 2 + (i - 1) / (n - 1) * pad_length
                dz = z - prev_z
                thenar_wp = thenar_wp.workplane(offset=dz).ellipse(sx, sy)

        try:
            thenar = thenar_wp.loft(combine=True)
            return thenar
        except Exception:
            # Fallback: simple box
            return (
                cq.Workplane("XY")
                .workplane(offset=pad_z_center - pad_length / 2)
                .center(pad_x_center, 0)
                .box(pad_width, pad_height, pad_length, centered=True)
            )

    # ----------------------------------------------------------------
    # Finger segments
    # ----------------------------------------------------------------
    def _build_finger_segment(
        self,
        base_x: float,
        base_y: float,
        base_z: float,
        length: float,
        base_diameter: float,
        tip_diameter: float,
        curl_angle_deg: float,
        parent_angle_deg: float = 0.0,
        is_joint: bool = False,
    ) -> tuple:
        """Build a single finger phalanx as a tapered cylinder."""
        total_angle = parent_angle_deg + curl_angle_deg
        angle_rad = math.radians(total_angle)

        dz = length * math.cos(angle_rad)
        dy_curl = -length * math.sin(angle_rad)

        end_x = base_x
        end_y = base_y + dy_curl
        end_z = base_z + dz

        base_r = base_diameter / 2
        tip_r = tip_diameter / 2

        # Interphalangeal joint widening: 10% wider at joint locations
        if is_joint:
            base_r *= 1.10

        segment = (
            cq.Workplane("XY")
            .workplane(offset=base_z)
            .center(base_x, base_y)
            .circle(base_r)
            .workplane(offset=dz)
            .center(0, dy_curl)
            .circle(tip_r)
            .loft(combine=True)
        )

        return segment, end_x, end_y, end_z, total_angle

    def _build_finger(
        self,
        knuckle_x: float,
        knuckle_z: float,
        total_length: float,
        grip_angle: float,
    ) -> cq.Workplane:
        """Build a complete 3-segment finger."""
        c = self.constraints
        ratios = c.finger_segment_ratios
        base_d = c.finger_base_diameter
        tip_d = c.finger_tip_diameter

        seg_lengths = [total_length * r for r in ratios]
        seg_diameters = [
            (base_d, base_d * 0.85),
            (base_d * 0.85, (base_d + tip_d) / 2),
            ((base_d + tip_d) / 2, tip_d),
        ]

        result = None
        cur_x = knuckle_x
        cur_y = 0.0
        cur_z = knuckle_z
        cur_angle = 0.0
        joint_angle = grip_angle / 3.0

        for i, (seg_len, (d_base, d_tip)) in enumerate(zip(seg_lengths, seg_diameters)):
            seg, cur_x, cur_y, cur_z, cur_angle = self._build_finger_segment(
                base_x=cur_x,
                base_y=cur_y,
                base_z=cur_z,
                length=seg_len,
                base_diameter=d_base,
                tip_diameter=d_tip,
                curl_angle_deg=joint_angle,
                parent_angle_deg=cur_angle,
                is_joint=(i > 0),
            )

            # Hemispherical fingertip on last segment
            if i == len(seg_lengths) - 1:
                try:
                    tip_cap = (
                        cq.Workplane("XY")
                        .workplane(offset=cur_z)
                        .center(cur_x, cur_y)
                        .sphere(d_tip / 2)
                    )
                    seg = seg.union(tip_cap)
                except Exception:
                    pass

            if result is None:
                result = seg
            else:
                result = result.union(seg)

            # Joint sphere between segments (15% oversized for visual definition)
            if i < len(seg_lengths) - 1:
                try:
                    joint_r = d_tip / 2 * 1.15
                    joint = (
                        cq.Workplane("XY")
                        .workplane(offset=cur_z)
                        .center(cur_x, cur_y)
                        .sphere(joint_r)
                    )
                    result = result.union(joint)
                except Exception:
                    pass

        return result

    # ----------------------------------------------------------------
    # Thumb — originates INSIDE palm with thenar bridge
    # ----------------------------------------------------------------
    def _build_thumb(self, palm_z: float) -> cq.Workplane:
        """Build a 2-segment thumb connected to the palm via thenar eminence.

        CRITICAL: The thumb base starts INSIDE the palm volume (at -palm_width*0.35)
        not outside it, ensuring geometric overlap and a connected solid
        after union. The thenar eminence provides additional bridging material.
        """
        c = self.constraints
        grip = c.grip_angle_deg
        abduction = math.radians(c.thumb_angle_deg)

        base_d = c.finger_base_diameter * 1.3  # thumb is thicker
        mid_d = (base_d + c.finger_tip_diameter * 1.3) / 2
        tip_d = c.finger_tip_diameter * 1.3
        total_length = c.thumb_length

        seg1_len = total_length * 0.55  # metacarpal
        seg2_len = total_length * 0.45  # distal

        # FIXED: Thumb origin is INSIDE the palm boundary
        # so the extruded geometry overlaps with the palm and creates
        # a solid union (no gap)
        origin_x = -c.palm_width * 0.35  # inside the palm, not at the edge
        origin_y = 0.0
        origin_z = palm_z + c.palm_length * 0.30  # lower third of palm

        # Segment 1: metacarpal — angles outward and forward
        dx1 = -seg1_len * math.sin(abduction)
        dz1 = seg1_len * math.cos(abduction)

        end1_x = origin_x + dx1
        end1_y = origin_y
        end1_z = origin_z + dz1

        # Build metacarpal as lofted tapered cylinder
        seg1 = (
            cq.Workplane("XY")
            .workplane(offset=origin_z)
            .center(origin_x, origin_y)
            .circle(base_d / 2)
            .workplane(offset=dz1)
            .center(dx1, 0)
            .circle(mid_d / 2)
            .loft(combine=True)
        )

        # Knuckle joint sphere at intersection
        try:
            knuckle = (
                cq.Workplane("XY")
                .workplane(offset=end1_z)
                .center(end1_x, end1_y)
                .sphere(mid_d / 2 * 1.15)
            )
            seg1 = seg1.union(knuckle)
        except Exception:
            pass

        # Segment 2: distal phalanx — continues with slight curl
        curl_rad = math.radians(grip * 0.4)
        dx2 = -seg2_len * math.sin(abduction) * math.cos(curl_rad)
        dz2 = seg2_len * math.cos(abduction) * math.cos(curl_rad)
        dy2 = -seg2_len * math.sin(curl_rad)

        end2_x = end1_x + dx2
        end2_y = end1_y + dy2
        end2_z = end1_z + dz2

        seg2 = (
            cq.Workplane("XY")
            .workplane(offset=end1_z)
            .center(end1_x, end1_y)
            .circle(mid_d / 2)
            .workplane(offset=dz2)
            .center(dx2, dy2)
            .circle(tip_d / 2)
            .loft(combine=True)
        )

        # Fingertip cap
        try:
            tip = (
                cq.Workplane("XY")
                .workplane(offset=end2_z)
                .center(end2_x, end2_y)
                .sphere(tip_d / 2)
            )
            seg2 = seg2.union(tip)
        except Exception:
            pass

        result = seg1.union(seg2)
        return result

    # ----------------------------------------------------------------
    # Metacarpal bridge (knuckle transitions)
    # ----------------------------------------------------------------
    def _build_metacarpal_bridge(self, palm_z: float) -> Optional[cq.Workplane]:
        """Build tapered cylinders from palm edge to each finger base."""
        c = self.constraints
        knuckle_z = palm_z + c.palm_length
        bridge_length = c.palm_length * 0.12
        bridge_z_start = knuckle_z - bridge_length

        finger_start_x = -(c.finger_spacing * 1.5)
        result = None

        for i in range(len(self.FINGER_NAMES)):
            finger_x = finger_start_x + i * c.finger_spacing
            base_d = c.finger_base_diameter

            try:
                bridge = (
                    cq.Workplane("XY")
                    .workplane(offset=bridge_z_start)
                    .center(finger_x, 0)
                    .circle(base_d / 2 * 1.15)
                    .workplane(offset=bridge_length)
                    .center(0, 0)
                    .circle(base_d / 2)
                    .loft(combine=True)
                )
                if result is None:
                    result = bridge
                else:
                    result = result.union(bridge)
            except Exception:
                pass

        return result

    # ----------------------------------------------------------------
    # Full hand assembly
    # ----------------------------------------------------------------
    def generate(self) -> cq.Workplane:
        """Generate the complete hand.

        Build order:
        1. Wrist connector (cylindrical plug)
        2. Palm (lofted ellipses)
        3. Thenar eminence (thumb pad, inside palm)
        4. Metacarpal bridge (knuckle transitions)
        5. 4 fingers (3 segments each)
        6. Thumb (2 segments, originates inside palm)
        """
        c = self.constraints

        # 1. Wrist connector
        wrist = self._build_wrist_connector()

        # 2. Anatomical palm
        palm = self._build_palm()
        palm_z = self.wrist_z + c.wrist_joint_length * 0.9
        knuckle_z = palm_z + c.palm_length

        # 3. Combine wrist + palm
        result = wrist.union(palm)

        # 4. Thenar eminence (ensures thumb attachment surface)
        try:
            thenar = self._build_thenar_eminence(palm_z)
            if thenar is not None:
                result = result.union(thenar)
        except Exception:
            pass

        # 5. Metacarpal bridge
        try:
            bridge = self._build_metacarpal_bridge(palm_z)
            if bridge is not None:
                result = result.union(bridge)
        except Exception:
            pass

        # 6. Build 4 fingers
        finger_start_x = -(c.finger_spacing * 1.5)

        for i, name in enumerate(self.FINGER_NAMES):
            finger_x = finger_start_x + i * c.finger_spacing
            finger_length = c.middle_finger_length * c.finger_length_ratios[i]

            try:
                finger = self._build_finger(
                    knuckle_x=finger_x,
                    knuckle_z=knuckle_z,
                    total_length=finger_length,
                    grip_angle=c.grip_angle_deg,
                )
                if finger is not None:
                    result = result.union(finger)
            except Exception:
                pass

        # 7. Build thumb — starts INSIDE palm for solid union
        try:
            thumb = self._build_thumb(palm_z)
            if thumb is not None:
                result = result.union(thumb)
        except Exception:
            pass

        self._result = result
        return result

    @property
    def result(self) -> Optional[cq.Workplane]:
        return self._result

    def get_total_length(self) -> float:
        """Total hand length from wrist connector to fingertip."""
        c = self.constraints
        return (
            c.wrist_joint_length * 0.9
            + c.palm_length
            + c.middle_finger_length
        )
