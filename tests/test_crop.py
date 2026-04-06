"""
Tests for the crop-box computation logic in app/processing.py.
"""
import pytest
from app.processing import compute_crop_box, MARGIN_TOP_FACTOR, MARGIN_SIDE_FACTOR, MARGIN_BOTTOM_FACTOR


class TestComputeCropBox:
    """Unit tests for compute_crop_box()."""

    def test_basic_crop_includes_face(self):
        """Crop rectangle must contain the entire face bounding box."""
        img_h, img_w = 1000, 800
        face_x, face_y, face_w, face_h = 0.3, 0.2, 0.2, 0.25
        x1, y1, x2, y2 = compute_crop_box(img_h, img_w, face_x, face_y, face_w, face_h)

        # Face absolute coords
        fx1 = face_x * img_w
        fy1 = face_y * img_h
        fx2 = fx1 + face_w * img_w
        fy2 = fy1 + face_h * img_h

        assert x1 <= fx1, "Crop left should be at or before face left"
        assert y1 <= fy1, "Crop top should be at or before face top"
        assert x2 >= fx2, "Crop right should be at or after face right"
        assert y2 >= fy2, "Crop bottom should be at or after face bottom"

    def test_shoulder_margin_below_face(self):
        """Bottom margin should be large enough to include shoulders."""
        img_h, img_w = 1000, 800
        face_x, face_y, face_w, face_h = 0.3, 0.1, 0.2, 0.2
        _, _, _, y2 = compute_crop_box(img_h, img_w, face_x, face_y, face_w, face_h)

        fh_px = face_h * img_h
        fy2_px = (face_y + face_h) * img_h

        # Bottom of crop must extend at least MARGIN_BOTTOM_FACTOR * face_h below face
        expected_min_y2 = fy2_px + MARGIN_BOTTOM_FACTOR * fh_px
        assert y2 >= min(expected_min_y2, img_h), (
            "Crop bottom should include shoulder margin"
        )

    def test_side_margins_symmetric(self):
        """Side margins should be symmetric around the face centre."""
        img_h, img_w = 1000, 800
        face_x, face_y, face_w, face_h = 0.35, 0.2, 0.3, 0.3
        x1, _, x2, _ = compute_crop_box(img_h, img_w, face_x, face_y, face_w, face_h)

        face_cx_px = (face_x + face_w / 2) * img_w
        left_dist  = face_cx_px - x1
        right_dist = x2 - face_cx_px
        assert abs(left_dist - right_dist) <= 2, (
            "Side margins should be approximately symmetric"
        )

    def test_top_margin_above_face(self):
        """Top margin must be at least MARGIN_TOP_FACTOR * face_h above the face."""
        img_h, img_w = 1000, 800
        face_x, face_y, face_w, face_h = 0.3, 0.3, 0.2, 0.2
        _, y1, _, _ = compute_crop_box(img_h, img_w, face_x, face_y, face_w, face_h)

        fh_px  = face_h * img_h
        fy1_px = face_y * img_h
        expected_max_y1 = fy1_px - MARGIN_TOP_FACTOR * fh_px
        assert y1 <= expected_max_y1, "Crop top should be above the face with margin"

    def test_clamped_to_image_boundary(self):
        """Crop must not exceed image dimensions."""
        img_h, img_w = 500, 400
        # Face near a corner – margins would exceed image bounds
        face_x, face_y, face_w, face_h = 0.0, 0.0, 0.5, 0.5
        x1, y1, x2, y2 = compute_crop_box(img_h, img_w, face_x, face_y, face_w, face_h)

        assert x1 >= 0
        assert y1 >= 0
        assert x2 <= img_w
        assert y2 <= img_h

    def test_large_face_clamped(self):
        """A face occupying most of the frame should still produce valid bounds."""
        img_h, img_w = 400, 300
        face_x, face_y, face_w, face_h = 0.0, 0.0, 1.0, 0.8
        x1, y1, x2, y2 = compute_crop_box(img_h, img_w, face_x, face_y, face_w, face_h)
        assert 0 <= x1 < x2 <= img_w
        assert 0 <= y1 < y2 <= img_h

    def test_output_is_int_tuple(self):
        """All returned values must be plain Python ints."""
        result = compute_crop_box(800, 600, 0.2, 0.2, 0.3, 0.3)
        assert all(isinstance(v, int) for v in result), "Expected int coordinates"
        assert len(result) == 4
