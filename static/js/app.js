/**
 * ID Photo Web – Frontend Logic
 *
 * Flow:
 *  1. User selects/drops files  → build gallery cards with original previews.
 *  2. User clicks "معالجة"      → POST /api/process, update cards with results.
 *  3. User clicks "تحميل ZIP"  → POST /api/download, stream ZIP file.
 */

"use strict";

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------
const dropZone      = document.getElementById("drop-zone");
const fileInput     = document.getElementById("file-input");
const browseBtn     = document.getElementById("browse-btn");
const actionBar     = document.getElementById("action-bar");
const processBtn    = document.getElementById("process-btn");
const clearBtn      = document.getElementById("clear-btn");
const downloadBtn   = document.getElementById("download-btn");
const gallery       = document.getElementById("gallery");
const progressWrap  = document.getElementById("progress-wrap");
const progressFill  = document.getElementById("progress-fill");
const progressLabel = document.getElementById("progress-label");
const presetSelect  = document.getElementById("preset");
const customFields  = document.getElementById("custom-size-fields");
const customWidth   = document.getElementById("custom-width");
const customHeight  = document.getElementById("custom-height");
const fmtSelect     = document.getElementById("output-format");

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let selectedFiles = [];           // File[]
let processedData = [];           // [{filename, image (b64), format}]

// ---------------------------------------------------------------------------
// Preset handling
// ---------------------------------------------------------------------------
presetSelect.addEventListener("change", () => {
  if (presetSelect.value === "custom") {
    customFields.hidden = false;
  } else {
    customFields.hidden = true;
    const [w, h] = presetSelect.value.split("x").map(Number);
    customWidth.value  = w;
    customHeight.value = h;
  }
});

function getTargetSize() {
  if (presetSelect.value === "custom") {
    return { width: Number(customWidth.value), height: Number(customHeight.value) };
  }
  const [w, h] = presetSelect.value.split("x").map(Number);
  return { width: w, height: h };
}

// ---------------------------------------------------------------------------
// Drag-and-drop
// ---------------------------------------------------------------------------
dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("drag-over");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  addFiles([...e.dataTransfer.files]);
});
dropZone.addEventListener("click", (e) => {
  if (e.target !== browseBtn) fileInput.click();
});
browseBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  fileInput.click();
});
fileInput.addEventListener("change", () => {
  addFiles([...fileInput.files]);
  fileInput.value = "";          // allow re-selecting same files
});

// ---------------------------------------------------------------------------
// File management
// ---------------------------------------------------------------------------
function addFiles(files) {
  const imageFiles = files.filter((f) => f.type.startsWith("image/"));
  if (!imageFiles.length) return;

  imageFiles.forEach((f) => {
    // Avoid duplicates by name
    if (selectedFiles.some((s) => s.name === f.name && s.size === f.size)) return;
    selectedFiles.push(f);
    buildCard(f);
  });

  actionBar.hidden = false;
  downloadBtn.hidden = true;
  processedData = [];
}

function clearAll() {
  selectedFiles = [];
  processedData = [];
  gallery.innerHTML = "";
  actionBar.hidden = true;
  downloadBtn.hidden = true;
  progressWrap.hidden = true;
}

clearBtn.addEventListener("click", clearAll);

// ---------------------------------------------------------------------------
// Gallery card
// ---------------------------------------------------------------------------
function buildCard(file) {
  const card = document.createElement("div");
  card.className = "photo-card";
  card.id = `card-f-${CSS.escape(file.name)}`;

  card.innerHTML = `
    <div class="photo-card__header" title="${escHtml(file.name)}">${escHtml(file.name)}</div>
    <div class="photo-card__previews">
      <div class="preview-box" dir="ltr">
        <span>الأصل</span>
        <img src="" alt="original" class="orig-img" />
      </div>
      <div class="preview-box" dir="ltr">
        <span>المعالجة</span>
        <div class="preview-placeholder">⏳</div>
      </div>
    </div>
    <div class="photo-card__status status-wait">⏳ في الانتظار</div>
  `;

  gallery.appendChild(card);

  // Load original thumbnail via FileReader
  const reader = new FileReader();
  reader.onload = (e) => {
    card.querySelector(".orig-img").src = e.target.result;
  };
  reader.readAsDataURL(file);
}

function updateCard(filename, result) {
  const card = document.getElementById(`card-f-${CSS.escape(filename)}`);
  if (!card) return;

  const previews   = card.querySelector(".photo-card__previews");
  const rightBox   = previews.children[1];   // processed preview box
  const statusEl   = card.querySelector(".photo-card__status");

  if (result.success) {
    const ext  = (result.format === "PNG") ? "png" : "jpeg";
    const span = document.createElement("span");
    span.textContent = "المعالجة";
    const img = document.createElement("img");
    img.src = `data:image/${ext};base64,${result.image}`;
    img.alt = "processed";
    rightBox.replaceChildren(span, img);
    statusEl.className  = "photo-card__status status-ok";
    statusEl.textContent = "✅ تمت المعالجة";
  } else {
    rightBox.innerHTML = `<span>المعالجة</span><div class="preview-placeholder">❌</div>`;
    statusEl.className  = "photo-card__status status-err";
    statusEl.textContent = `❌ ${result.error || "خطأ غير معروف"}`;
  }
}

// ---------------------------------------------------------------------------
// Processing
// ---------------------------------------------------------------------------
processBtn.addEventListener("click", async () => {
  if (!selectedFiles.length) return;

  processBtn.disabled = true;
  clearBtn.disabled   = true;
  downloadBtn.hidden  = true;
  processedData       = [];

  const { width, height } = getTargetSize();
  const format = fmtSelect.value;

  // Reset all cards to "waiting"
  selectedFiles.forEach((f) => {
    const card = document.getElementById(`card-f-${CSS.escape(f.name)}`);
    if (card) {
      const rightBox = card.querySelector(".photo-card__previews").children[1];
      rightBox.innerHTML = `<span>المعالجة</span><div class="preview-placeholder">⏳</div>`;
      const statusEl = card.querySelector(".photo-card__status");
      statusEl.className  = "photo-card__status status-wait";
      statusEl.textContent = "⏳ جاري المعالجة…";
    }
  });

  // Process in batches of 5 to avoid large payloads
  const BATCH = 5;
  let done = 0;

  progressWrap.hidden = false;
  setProgress(0, `معالجة 0 / ${selectedFiles.length}`);

  for (let i = 0; i < selectedFiles.length; i += BATCH) {
    const batch = selectedFiles.slice(i, i + BATCH);
    const form  = new FormData();
    form.append("width",         width);
    form.append("height",        height);
    form.append("output_format", format);
    batch.forEach((f) => form.append("files[]", f));

    try {
      const resp = await fetch("/api/process", { method: "POST", body: form });
      if (!resp.ok) throw new Error(`Server error ${resp.status}`);
      const results = await resp.json();

      results.forEach((r) => {
        updateCard(r.filename, r);
        if (r.success) processedData.push(r);
      });
    } catch (err) {
      batch.forEach((f) => {
        updateCard(f.name, { success: false, error: err.message });
      });
    }

    done += batch.length;
    setProgress(
      Math.round((done / selectedFiles.length) * 100),
      `معالجة ${done} / ${selectedFiles.length}`
    );
  }

  setProgress(100, "اكتملت المعالجة ✅");
  processBtn.disabled = false;
  clearBtn.disabled   = false;

  if (processedData.length > 0) downloadBtn.hidden = false;
});

function setProgress(pct, label) {
  progressFill.style.width = `${pct}%`;
  progressLabel.textContent = label;
}

// ---------------------------------------------------------------------------
// ZIP Download
// ---------------------------------------------------------------------------
downloadBtn.addEventListener("click", async () => {
  if (!processedData.length) return;

  downloadBtn.disabled = true;

  try {
    const resp = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(processedData),
    });

    if (!resp.ok) throw new Error(`Server error ${resp.status}`);

    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = "id_photos.zip";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert("فشل تحميل الملف: " + err.message);
  } finally {
    downloadBtn.disabled = false;
  }
});

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function escHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
