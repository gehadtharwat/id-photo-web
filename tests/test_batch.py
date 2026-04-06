"""
Tests for the Flask API endpoints in app/main.py.

Covers:
- GET /          returns 200 with HTML
- POST /api/process  returns correct count, handles unsupported files
- POST /api/download bundles results into a ZIP
"""
import base64
import io
import json
import zipfile

import numpy as np
import pytest
from PIL import Image

from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jpeg_bytes(width: int = 200, height: int = 200) -> bytes:
    """Return raw bytes of a small solid-colour JPEG image."""
    arr = np.full((height, width, 3), (150, 100, 50), dtype=np.uint8)
    pil = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    pil.save(buf, format="JPEG")
    return buf.getvalue()


def _make_png_bytes(width: int = 100, height: int = 100) -> bytes:
    """Return raw bytes of a small solid-colour PNG image."""
    arr = np.full((height, width, 3), (200, 180, 160), dtype=np.uint8)
    pil = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIndex:
    def test_get_root_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_get_root_returns_html(self, client):
        resp = client.get("/")
        assert b"<!DOCTYPE html>" in resp.data or b"<html" in resp.data


class TestApiProcess:
    def test_no_files_returns_400(self, client):
        resp = client.post("/api/process")
        assert resp.status_code == 400

    def test_returns_one_result_per_file(self, client):
        """Endpoint should return a list of the same length as uploaded files."""
        img1 = _make_jpeg_bytes()
        img2 = _make_jpeg_bytes()
        data = {
            "files[]": [
                (io.BytesIO(img1), "photo1.jpg", "image/jpeg"),
                (io.BytesIO(img2), "photo2.jpg", "image/jpeg"),
            ],
            "width": "200",
            "height": "200",
        }
        resp = client.post(
            "/api/process",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        results = resp.get_json()
        assert isinstance(results, list)
        assert len(results) == 2

    def test_unsupported_file_type_reports_error(self, client):
        """Uploading a text file as image/* should return success=False."""
        data = {
            "files[]": [(io.BytesIO(b"not an image"), "doc.txt", "text/plain")],
            "width": "200",
            "height": "200",
        }
        resp = client.post(
            "/api/process",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        results = resp.get_json()
        assert len(results) == 1
        assert results[0]["success"] is False
        assert results[0]["error"] is not None

    def test_per_file_error_does_not_abort_batch(self, client):
        """One bad file in a batch should not prevent others from being attempted."""
        img_ok  = _make_jpeg_bytes()
        data = {
            "files[]": [
                (io.BytesIO(b"garbage"), "bad.jpg",  "image/jpeg"),
                (io.BytesIO(img_ok),    "good.jpg", "image/jpeg"),
            ],
            "width": "200",
            "height": "200",
        }
        resp = client.post(
            "/api/process",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        results = resp.get_json()
        # Both files must be represented in the response
        assert len(results) == 2

    def test_invalid_dimensions_return_400(self, client):
        img = _make_jpeg_bytes()
        for w, h in [("0", "200"), ("200", "-1"), ("abc", "200")]:
            data = {
                "files[]": [(io.BytesIO(img), "photo.jpg", "image/jpeg")],
                "width": w,
                "height": h,
            }
            resp = client.post(
                "/api/process",
                data=data,
                content_type="multipart/form-data",
            )
            assert resp.status_code == 400, f"Expected 400 for w={w}, h={h}"

    def test_result_filenames_match_uploads(self, client):
        img = _make_jpeg_bytes()
        data = {
            "files[]": [(io.BytesIO(img), "myface.jpg", "image/jpeg")],
            "width": "200",
            "height": "200",
        }
        resp = client.post(
            "/api/process",
            data=data,
            content_type="multipart/form-data",
        )
        results = resp.get_json()
        assert results[0]["filename"] == "myface.jpg"


class TestApiDownload:
    def _make_payload(self, names=("img1.jpg",), fmt="JPEG"):
        """Build a JSON payload with fake processed images."""
        img_bytes = _make_jpeg_bytes(50, 50)
        encoded = base64.b64encode(img_bytes).decode()
        return [
            {"filename": name, "image": encoded, "format": fmt}
            for name in names
        ]

    def test_returns_zip_content_type(self, client):
        payload = self._make_payload()
        resp = client.post(
            "/api/download",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert "zip" in resp.content_type

    def test_zip_contains_correct_file_count(self, client):
        names = ["a.jpg", "b.jpg", "c.jpg"]
        payload = self._make_payload(names=names)
        resp = client.post(
            "/api/download",
            data=json.dumps(payload),
            content_type="application/json",
        )
        zip_buf = io.BytesIO(resp.data)
        with zipfile.ZipFile(zip_buf) as zf:
            assert len(zf.namelist()) == len(names)

    def test_zip_filenames_have_id_suffix(self, client):
        payload = self._make_payload(names=["photo.jpg"])
        resp = client.post(
            "/api/download",
            data=json.dumps(payload),
            content_type="application/json",
        )
        zip_buf = io.BytesIO(resp.data)
        with zipfile.ZipFile(zip_buf) as zf:
            assert "photo_id.jpg" in zf.namelist()

    def test_empty_payload_returns_empty_zip(self, client):
        resp = client.post(
            "/api/download",
            data=json.dumps([]),
            content_type="application/json",
        )
        assert resp.status_code == 200
        zip_buf = io.BytesIO(resp.data)
        with zipfile.ZipFile(zip_buf) as zf:
            assert zf.namelist() == []

    def test_invalid_body_returns_400(self, client):
        resp = client.post(
            "/api/download",
            data="not json",
            content_type="application/json",
        )
        assert resp.status_code == 400
