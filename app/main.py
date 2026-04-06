"""
Flask web application for ID photo generation.

Endpoints
---------
GET  /                – Serve the main UI page.
POST /api/process     – Accept one or more image files, run the processing
                        pipeline, and return per-file results as JSON (base64
                        encoded processed images + error messages).
POST /api/download    – Accept the same set of processed images (base64) and
                        return them bundled in a ZIP file.
"""

from __future__ import annotations

import base64
import io
import json
import zipfile
from typing import Any, Dict, List

from flask import Flask, jsonify, render_template, request, send_file

from app.processing import process_image

app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static",
)

# Maximum upload size: 16 MB per request
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

# Allowed MIME types for uploaded images
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/process")
def api_process():
    """
    Process uploaded images.

    Form fields
    -----------
    files[]       : one or more image files
    width         : target width in pixels (default 413 → 3.5 cm @ 300 dpi)
    height        : target height in pixels (default 531 → 4.5 cm @ 300 dpi)
    output_format : "JPEG" or "PNG" (default "JPEG")

    Response
    --------
    JSON array, one object per uploaded file:
    {
      "filename": "photo.jpg",
      "success": true,
      "image": "<base64-encoded output>",   // only on success
      "error": null                           // or error message string
    }
    """
    files = request.files.getlist("files[]")
    if not files:
        return jsonify({"error": "No files uploaded."}), 400

    try:
        width = int(request.form.get("width", 413))
        height = int(request.form.get("height", 531))
    except ValueError:
        return jsonify({"error": "width and height must be integers."}), 400

    if width <= 0 or height <= 0:
        return jsonify({"error": "width and height must be positive."}), 400

    output_format = request.form.get("output_format", "JPEG").upper()
    if output_format not in ("JPEG", "PNG"):
        output_format = "JPEG"

    results: List[Dict[str, Any]] = []

    for f in files:
        filename = f.filename or "unknown"

        if f.mimetype not in ALLOWED_TYPES:
            results.append(
                {
                    "filename": filename,
                    "success": False,
                    "image": None,
                    "error": f"Unsupported file type: {f.mimetype}.",
                }
            )
            continue

        image_bytes = f.read()
        result = process_image(image_bytes, width, height, output_format)

        if result.success:
            encoded = base64.b64encode(result.processed_image).decode("utf-8")
            results.append(
                {
                    "filename": filename,
                    "success": True,
                    "image": encoded,
                    "error": None,
                    "format": output_format,
                }
            )
        else:
            results.append(
                {
                    "filename": filename,
                    "success": False,
                    "image": None,
                    "error": result.error,
                }
            )

    return jsonify(results)


@app.post("/api/download")
def api_download():
    """
    Bundle processed images into a ZIP file and return it.

    Request body (JSON)
    -------------------
    [
      {"filename": "photo.jpg", "image": "<base64>", "format": "JPEG"},
      ...
    ]
    """
    data = request.get_json(silent=True)
    if data is None or not isinstance(data, list):
        return jsonify({"error": "Invalid request body."}), 400

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in data:
            filename = item.get("filename", "image")
            b64 = item.get("image", "")
            fmt = item.get("format", "JPEG").upper()

            try:
                img_bytes = base64.b64decode(b64)
            except Exception:
                continue

            # Determine output filename extension
            ext = "jpg" if fmt == "JPEG" else "png"
            base = filename.rsplit(".", 1)[0] if "." in filename else filename
            out_name = f"{base}_id.{ext}"

            zf.writestr(out_name, img_bytes)

    zip_buf.seek(0)
    return send_file(
        zip_buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="id_photos.zip",
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
