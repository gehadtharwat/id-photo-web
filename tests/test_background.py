"""
Tests for composite_on_white() in app/processing.py.
"""
import numpy as np
import pytest

from app.processing import composite_on_white


class TestCompositeOnWhite:
    """Verify that the background compositing uses a pure-white (#FFFFFF) background."""

    def _make_bgr(self, h: int = 100, w: int = 100) -> np.ndarray:
        """Create a solid dark-blue test image in BGR."""
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:, :] = (180, 50, 10)   # dark blueish colour in BGR
        return img

    def test_full_foreground_mask_keeps_original(self):
        """When mask is all-1 (all foreground) the output should equal the input."""
        img = self._make_bgr()
        mask = np.ones((100, 100), dtype=np.float32)
        result = composite_on_white(img, mask)
        np.testing.assert_array_equal(result, img)

    def test_zero_mask_produces_white_background(self):
        """When mask is all-0 (all background) the output should be pure white."""
        img = self._make_bgr()
        mask = np.zeros((100, 100), dtype=np.float32)
        result = composite_on_white(img, mask)
        expected = np.ones((100, 100, 3), dtype=np.uint8) * 255
        np.testing.assert_array_equal(result, expected)

    def test_partial_mask_background_pixels_are_white(self):
        """Pixels where mask == 0 must be (255, 255, 255) regardless of source colour."""
        img = self._make_bgr()
        mask = np.ones((100, 100), dtype=np.float32)
        mask[:, 50:] = 0.0   # right half is background
        result = composite_on_white(img, mask)

        right_half = result[:, 50:, :]
        assert np.all(right_half == 255), (
            "All background pixels (mask=0) must be pure white (255,255,255)"
        )

    def test_output_dtype_is_uint8(self):
        """Output array should be uint8 (values 0-255)."""
        img  = self._make_bgr()
        mask = np.ones((100, 100), dtype=np.float32) * 0.5
        result = composite_on_white(img, mask)
        assert result.dtype == np.uint8

    def test_output_shape_matches_input(self):
        """Output shape must equal input image shape."""
        img  = self._make_bgr(h=80, w=60)
        mask = np.ones((80, 60), dtype=np.float32)
        result = composite_on_white(img, mask)
        assert result.shape == img.shape

    def test_3d_mask_accepted(self):
        """A 3-channel mask (H,W,3) should be handled without error."""
        img  = self._make_bgr()
        mask = np.zeros((100, 100, 3), dtype=np.float32)
        result = composite_on_white(img, mask)
        # All background → white
        np.testing.assert_array_equal(result, np.full_like(img, 255))

    def test_blended_pixel_values(self):
        """With mask=0.5 the output pixel should be the average of source and white."""
        # Use a single-channel mask for clarity; source pixel is (100, 100, 100)
        src = np.full((1, 1, 3), 100, dtype=np.uint8)
        mask = np.full((1, 1), 0.5, dtype=np.float32)
        result = composite_on_white(src, mask)
        # 100*0.5 + 255*0.5 = 177.5 → 177 after clip+cast
        expected = np.full((1, 1, 3), 177, dtype=np.uint8)
        np.testing.assert_array_equal(result, expected)
