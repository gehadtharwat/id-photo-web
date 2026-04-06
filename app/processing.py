"""
Image processing pipeline for ID photo generation.
Steps per image:
  1. Detect face with MediaPipe Face Detection.
  2. Compute a crop rectangle that includes the full face + shoulders.
  3. Segment the person from the background using MediaPipe Selfie Segmentation.
  4. Composite segmented person onto a pure white (#FFFFFF) background.
  5. Resize to the requested target dimensions.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Margin factors applied to the detected face bounding box (relative to the
# face height/width) when computing the crop rectangle.
# These values produce a "head-and-shoulders" framing consistent with most
# national ID requirements.
MARGIN_TOP_FACTOR = 0.40      # space above the top of the face
MARGIN_SIDE_FACTOR = 0.40     # space on each side of the face
MARGIN_BOTTOM_FACTOR = 1.20   # space below the chin (for shoulders)

# Minimum crop size in pixels to avoid degenerate outputs.
MIN_CROP_PX = 64

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class ProcessingResult:
    """Return value of :func:`process_image`."""

    success: bool
    processed_image: Optional[bytes] = None   # JPEG/PNG bytes
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_bgr_array(image_bytes: bytes) -> np.ndarray:
    """Decode arbitrary image bytes into a BGR uint8 NumPy array."""
    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Unable to decode image bytes.")
    return img


def compute_crop_box(
    img_h: int,
    img_w: int,
    face_x: float,
    face_y: float,
    face_w: float,
    face_h: float,
) -> Tuple[int, int, int, int]:
    """
    Given a normalised face bounding box (values in [0, 1]) and the image
    dimensions, return an integer crop rectangle ``(x1, y1, x2, y2)`` in
    pixel coordinates that includes the full face plus shoulder room.

    The crop is clamped to the image boundary.
    """
    # Convert normalised coordinates to absolute pixels
    fx1 = face_x * img_w
    fy1 = face_y * img_h
    fw = face_w * img_w
    fh = face_h * img_h

    top_margin = MARGIN_TOP_FACTOR * fh
    side_margin = MARGIN_SIDE_FACTOR * fw
    bottom_margin = MARGIN_BOTTOM_FACTOR * fh

    x1 = int(fx1 - side_margin)
    y1 = int(fy1 - top_margin)
    x2 = int(fx1 + fw + side_margin)
    y2 = int(fy1 + fh + bottom_margin)

    # Clamp to image boundaries
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(img_w, x2)
    y2 = min(img_h, y2)

    return x1, y1, x2, y2


def composite_on_white(
    bgr_img: np.ndarray,
    mask: np.ndarray,
) -> np.ndarray:
    """
    Composite *bgr_img* onto a pure white background using *mask*.

    Parameters
    ----------
    bgr_img:
        Source image in BGR uint8 format.
    mask:
        Float32 mask in [0, 1] where 1 = foreground (person).

    Returns
    -------
    BGR uint8 image on a white background.
    """
    if mask.ndim == 2:
        mask_3 = np.stack([mask] * 3, axis=-1)
    else:
        mask_3 = mask

    white = np.ones_like(bgr_img, dtype=np.float32) * 255.0
    result = bgr_img.astype(np.float32) * mask_3 + white * (1.0 - mask_3)
    return np.clip(result, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def process_image(
    image_bytes: bytes,
    target_width: int,
    target_height: int,
    output_format: str = "JPEG",
) -> ProcessingResult:
    """
    Full processing pipeline for a single image.

    Parameters
    ----------
    image_bytes:
        Raw bytes of the uploaded image file.
    target_width, target_height:
        Output dimensions in pixels.
    output_format:
        ``"JPEG"`` or ``"PNG"``.

    Returns
    -------
    :class:`ProcessingResult` with ``success=True`` and JPEG/PNG bytes on
    success, or ``success=False`` and an error message on failure.
    """
    try:
        bgr = _to_bgr_array(image_bytes)
    except ValueError as exc:
        return ProcessingResult(success=False, error=str(exc))

    img_h, img_w = bgr.shape[:2]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    # ------------------------------------------------------------------
    # Step 1 – Face detection
    # ------------------------------------------------------------------
    face_detection = mp.solutions.face_detection.FaceDetection(
        model_selection=1,  # full-range model
        min_detection_confidence=0.5,
    )
    with face_detection:
        results = face_detection.process(rgb)

    if not results.detections:
        return ProcessingResult(success=False, error="No face detected.")

    # Use the first detected face
    det = results.detections[0]
    bbox = det.location_data.relative_bounding_box
    x1, y1, x2, y2 = compute_crop_box(
        img_h, img_w,
        bbox.xmin, bbox.ymin,
        bbox.width, bbox.height,
    )

    # Validate crop size
    if (x2 - x1) < MIN_CROP_PX or (y2 - y1) < MIN_CROP_PX:
        return ProcessingResult(
            success=False,
            error="Detected face is too small for cropping.",
        )

    # ------------------------------------------------------------------
    # Step 2 – Background segmentation on the full image
    # ------------------------------------------------------------------
    selfie_seg = mp.solutions.selfie_segmentation.SelfieSegmentation(
        model_selection=1  # landscape model (better quality)
    )
    with selfie_seg:
        seg_results = selfie_seg.process(rgb)

    # seg_mask is a float32 array with values in [0, 1]
    seg_mask = seg_results.segmentation_mask  # shape (H, W)

    # ------------------------------------------------------------------
    # Step 3 – Composite onto white background
    # ------------------------------------------------------------------
    composited = composite_on_white(bgr, seg_mask)

    # ------------------------------------------------------------------
    # Step 4 – Crop to head-and-shoulders region
    # ------------------------------------------------------------------
    cropped = composited[y1:y2, x1:x2]

    # ------------------------------------------------------------------
    # Step 5 – Resize to target dimensions
    # ------------------------------------------------------------------
    resized = cv2.resize(
        cropped,
        (target_width, target_height),
        interpolation=cv2.INTER_LANCZOS4,
    )

    # ------------------------------------------------------------------
    # Step 6 – Encode output
    # ------------------------------------------------------------------
    pil_img = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))

    buf = io.BytesIO()
    fmt = output_format.upper()
    if fmt not in ("JPEG", "PNG"):
        fmt = "JPEG"
    save_kwargs = {"quality": 95} if fmt == "JPEG" else {}
    pil_img.save(buf, format=fmt, **save_kwargs)

    return ProcessingResult(success=True, processed_image=buf.getvalue())
