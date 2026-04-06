# ID Photo Web

A web application that converts regular photos into **ID-ready images**:
- Full face visible, shoulders included (head-and-shoulders framing)
- Pure white background (#FFFFFF) via AI segmentation
- No modification of facial features
- Configurable output size (preset or custom)
- Batch upload with per-image preview and ZIP download

Built with **Flask**, **MediaPipe** (face detection + selfie segmentation), **OpenCV**, and vanilla JavaScript.

---

## Local Setup

### Prerequisites

- Python 3.10 or later
- `pip`

### Install dependencies

```bash
pip install -r requirements.txt
```

---

## Run the Server

```bash
python run.py
```

The server listens on **http://localhost:5000** by default.

Alternatively, using Flask's CLI:

```bash
flask --app app.main run --debug
```

---

## How to Use the UI

1. **Open** http://localhost:5000 in your browser.
2. **Choose output settings** (top panel):
   - *مقاس الصورة*: select a preset (e.g., passport 3.5×4.5 cm) or *مخصّص* for custom pixel dimensions.
   - *صيغة الملف*: JPEG or PNG.
3. **Upload photos**: drag-and-drop images onto the upload area, or click *اختر ملفات*.
4. Click **🚀 معالجة الصور** to process. Each card shows the original and processed previews with a status badge.
5. Click **⬇️ تحميل ZIP** to download all successfully processed images as a ZIP archive.

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Project Structure

```
id-photo-web/
├── app/
│   ├── __init__.py
│   ├── main.py          # Flask routes
│   └── processing.py   # Image processing pipeline
├── static/
│   ├── css/style.css
│   └── js/app.js
├── templates/
│   └── index.html
├── tests/
│   ├── test_crop.py        # Crop-box logic tests
│   ├── test_background.py  # Background compositing tests
│   └── test_batch.py       # Flask API / batch endpoint tests
├── run.py
├── requirements.txt
└── README.md
```

---

## Limitations

- **Photo quality**: The pipeline works best with clear, well-lit, front-facing portraits. Very dark, blurry, or heavily compressed images may produce poor results.
- **Occlusions**: Hats, sunglasses, masks, or other occlusions covering the face will cause face detection to fail ("No face detected" error).
- **Multiple faces**: Only the **first** detected face is processed. Images with multiple people will be cropped around the largest/most-confident detection.
- **Extreme poses**: Profile or strongly tilted views may not be detected reliably.
- **Transparency**: PNG output preserves the alpha channel for fully transparent backgrounds if needed, but the compositing step fills the background with white before saving.
- **Processing time**: MediaPipe models run on CPU; processing a batch of many high-resolution photos may take several seconds per image.
