/**
 * Pepper AI — Ingest / Upload JavaScript
 */
'use strict';

let selectedFile = null;
let pollingInterval = null;

const dropZone   = document.getElementById('dropZone');
const videoInput = document.getElementById('videoInput');
const uploadForm = document.getElementById('uploadForm');
const fileInfo   = document.getElementById('fileInfo');

// ── Drag & Drop ─────────────────────────────────────────────
if (dropZone) {
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('video/')) handleFileSelect(file);
    else showToast('Please drop a video file', 'error');
  });
  dropZone.addEventListener('click', () => videoInput && videoInput.click());
}

if (videoInput) {
  videoInput.addEventListener('change', () => {
    if (videoInput.files[0]) handleFileSelect(videoInput.files[0]);
  });
}

function handleFileSelect(file) {
  selectedFile = file;
  const mb = (file.size / 1024 / 1024).toFixed(1);
  const gb = (file.size / 1024 / 1024 / 1024).toFixed(2);
  const sizeStr = file.size > 1024 * 1024 * 1024 ? `${gb} GB` : `${mb} MB`;

  if (fileInfo) fileInfo.textContent = `📎 ${file.name}  (${sizeStr})`;

  const titleInput = document.getElementById('titleInput');
  if (titleInput && !titleInput.value) {
    titleInput.value = file.name.replace(/\.[^.]+$/, '').replace(/[_\-]+/g, ' ');
  }

  if (dropZone) dropZone.style.display = 'none';
  if (uploadForm) uploadForm.style.display = 'block';
}

function cancelUpload() {
  selectedFile = null;
  if (videoInput) videoInput.value = '';
  if (uploadForm) uploadForm.style.display = 'none';
  if (dropZone)   dropZone.style.display = '';
  const pw = document.getElementById('progressWrap');
  if (pw) pw.style.display = 'none';
  stopPolling();
}

// ── Upload ──────────────────────────────────────────────────
async function startUpload() {
  if (!selectedFile) { showToast('Please select a file', 'error'); return; }
  const title = document.getElementById('titleInput')?.value.trim();
  if (!title) { showToast('Please enter a title', 'error'); return; }

  const uploadBtn = document.getElementById('uploadBtn');
  if (uploadBtn) { uploadBtn.disabled = true; uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading...'; }

  const progressWrap = document.getElementById('progressWrap');
  const progressBar  = document.getElementById('uploadProgress');
  const progressText = document.getElementById('progressText');
  const progressPct  = document.getElementById('progressPct');
  if (progressWrap) progressWrap.style.display = 'block';

  const contentType = document.querySelector('input[name="contentType"]:checked')?.value || 'episode';

  const fd = new FormData();
  fd.append('video',        selectedFile);
  fd.append('title',        title);
  fd.append('network',      document.getElementById('networkInput')?.value  || 'ZEE');
  fd.append('language',     document.getElementById('languageInput')?.value || 'Hindi');
  fd.append('genre',        document.getElementById('genreInput')?.value    || 'Drama');
  fd.append('content_type', contentType);

  const xhr = new XMLHttpRequest();

  xhr.upload.addEventListener('progress', (e) => {
    if (e.lengthComputable) {
      const pct = Math.round(e.loaded / e.total * 88);
      if (progressBar) progressBar.style.width = pct + '%';
      if (progressPct) progressPct.textContent = pct + '%';
      if (progressText) {
        if (pct < 30)      progressText.textContent = 'Uploading file...';
        else if (pct < 70) progressText.textContent = 'Transferring...';
        else               progressText.textContent = 'Finalizing upload...';
      }
    }
  });

  xhr.addEventListener('load', () => {
    try {
      const data = JSON.parse(xhr.responseText);
      if (data.success) {
        if (progressBar)  progressBar.style.width  = '100%';
        if (progressPct)  progressPct.textContent   = '100%';
        if (progressText) progressText.textContent  = '✅ Upload complete! AI pipeline starting...';
        if (uploadBtn) uploadBtn.innerHTML = '<i class="fas fa-cogs fa-spin"></i> Pipeline Running...';
        showToast('Upload complete! AI processing started.', 'success', 5000);
        startPolling(data.video_id);
      } else {
        showToast(data.error || 'Upload failed', 'error');
        resetUploadBtn();
      }
    } catch (e) {
      showToast('Upload response error', 'error');
      resetUploadBtn();
    }
  });

  xhr.addEventListener('error', () => { showToast('Network error during upload', 'error'); resetUploadBtn(); });
  xhr.open('POST', '/api/upload');
  xhr.send(fd);
}

function resetUploadBtn() {
  const btn = document.getElementById('uploadBtn');
  if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-rocket"></i> Start Processing'; }
}

// ── Pipeline Polling ────────────────────────────────────────
const STATUS_INFO = {
  'UPLOADED':             { pct: 10,  label: '📥 File uploaded and queued' },
  'VALIDATED':            { pct: 20,  label: '✅ File validated successfully' },
  'PROCESSING':           { pct: 35,  label: '⚙️ Extracting video info...' },
  'CLIPS_READY':          { pct: 55,  label: '✂️ Scenes detected & clips extracted!' },
  'METADATA_GENERATED':   { pct: 70,  label: '🤖 Gemini AI metadata generated!' },
  'THUMBNAILS_GENERATED': { pct: 82,  label: '🖼️ Branded thumbnails created!' },
  'QA_DONE':              { pct: 92,  label: '🛡️ Quality assurance complete!' },
  'REVIEW_PENDING':       { pct: 100, label: '👁️ Ready for manual review!' },
  'ERROR':                { pct: 100, label: '❌ Pipeline error occurred' },
};

function startPolling(videoId) {
  stopPolling();
  pollingInterval = setInterval(() => pollStatus(videoId), 4500);
  setTimeout(() => pollStatus(videoId), 1500);
}

function stopPolling() {
  if (pollingInterval) { clearInterval(pollingInterval); pollingInterval = null; }
}

async function pollStatus(videoId) {
  try {
    const r  = await fetch(`/api/video/${videoId}/status`);
    const d  = await r.json();
    const info = STATUS_INFO[d.status] || { pct: d.progress || 0, label: d.status };

    const pb  = document.getElementById('uploadProgress');
    const pt  = document.getElementById('progressText');
    const pct = document.getElementById('progressPct');
    const feed= document.getElementById('pipelineStatus');

    if (pb)  pb.style.width    = info.pct + '%';
    if (pct) pct.textContent   = info.pct + '%';
    if (pt)  pt.textContent    = info.label;

    if (feed && d.events && d.events.length > 0) {
      feed.innerHTML = d.events.slice(0, 10).map(ev =>
        `<div class="pipe-event">▸ ${ev.msg}</div>`
      ).join('');
    }

    if (d.status === 'REVIEW_PENDING') {
      stopPolling();
      showToast(`🎉 ${d.clips_count} clips are ready for review!`, 'success', 7000);
      setTimeout(() => { window.location.href = '/review'; }, 3500);
    } else if (d.status === 'ERROR') {
      stopPolling();
      showToast('❌ Pipeline error: ' + (d.error || 'Check logs'), 'error', 10000);
    }
  } catch (_) { /* ignore transient poll errors */ }
}
