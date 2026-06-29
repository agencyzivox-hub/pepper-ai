/**
 * Pepper AI — Publish to YouTube JavaScript
 */
'use strict';

let scheduleClipId = null;

// ── Tab switching ────────────────────────────────────────────
function switchTab(tab, btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  const el = document.getElementById(`tab-${tab}`);
  if (el) el.classList.add('active');
}

// ── Publish Now ──────────────────────────────────────────────
async function publishNow(clipId, btn) {
  if (!confirm('Publish this clip to YouTube as PUBLIC video now?')) return;
  const origHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Publishing...';

  const statusEl = document.getElementById(`pubstatus-${clipId}`);
  if (statusEl) statusEl.textContent = '⏳ Connecting to YouTube API...';

  try {
    const r = await fetch(`/api/clip/${clipId}/publish`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({})
    });
    const d = await r.json();
    if (d.success) {
      showToast('🚀 YouTube upload started! This may take a few minutes.', 'success', 8000);
      if (statusEl) statusEl.textContent = '⏳ Uploading to YouTube... Do not close this page.';
      btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading...';
      // Poll for completion
      pollPublishStatus(clipId, btn, origHtml, statusEl);
    } else {
      showToast(d.error || 'Publish failed', 'error');
      btn.disabled = false;
      btn.innerHTML = origHtml;
      if (statusEl) statusEl.textContent = '❌ ' + (d.error || 'Failed');
    }
  } catch (e) {
    showToast('Network error: ' + e.message, 'error');
    btn.disabled = false;
    btn.innerHTML = origHtml;
  }
}

async function pollPublishStatus(clipId, btn, origHtml, statusEl, attempts = 0) {
  if (attempts > 60) { // max 5 minutes
    if (statusEl) statusEl.textContent = '⏳ Upload in progress (check YouTube Studio)';
    if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
    return;
  }
  try {
    const cr = await fetch(`/api/clip/${clipId}/status`);
    const cd = await cr.json();

    if (cd.status === 'PUBLISHED') {
      showToast('✅ Published to YouTube successfully!', 'success', 8000);
      if (statusEl) {
        statusEl.innerHTML = cd.yt_url
          ? `✅ Published! <a href="${cd.yt_url}" target="_blank" style="color:var(--primary)">View on YouTube →</a>`
          : '✅ Published!';
      }
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = cd.yt_url
          ? `<a href="${cd.yt_url}" target="_blank" style="color:#fff;text-decoration:none"><i class="fab fa-youtube"></i> View</a>`
          : '<i class="fab fa-youtube"></i> Published';
        btn.style.background = 'rgba(80,200,120,0.3)';
      }
      // Refresh page after 3s
      setTimeout(() => location.reload(), 3000);
      return;
    } else if (cd.status === 'APPROVED' && attempts > 3) {
      // Upload may have failed silently
      if (statusEl) statusEl.textContent = '⚠️ Upload may have failed. Check YouTube Studio.';
      if (btn) { btn.disabled = false; btn.innerHTML = origHtml; }
      return;
    }
  } catch (_) {}
  setTimeout(() => pollPublishStatus(clipId, btn, origHtml, statusEl, attempts + 1), 5000);
}

// ── Schedule ─────────────────────────────────────────────────
function openSchedule(clipId) {
  scheduleClipId = clipId;
  // Set min datetime to now + 10 minutes
  const input = document.getElementById('scheduleInput');
  if (input) {
    const now = new Date(Date.now() + 10 * 60 * 1000);
    input.min = now.toISOString().slice(0, 16);
    input.value = new Date(Date.now() + 60 * 60 * 1000).toISOString().slice(0, 16);
  }
  openModal('scheduleModal');
}

async function confirmSchedule() {
  if (!scheduleClipId) return;
  const input = document.getElementById('scheduleInput');
  if (!input || !input.value) { showToast('Please select a date/time', 'error'); return; }

  try {
    const r = await fetch(`/api/clip/${scheduleClipId}/publish`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ schedule_at: input.value })
    });
    const d = await r.json();
    if (d.success && d.scheduled) {
      showToast('✅ Clip scheduled successfully!', 'success');
      closeModal('scheduleModal');
      setTimeout(() => location.reload(), 1000);
    } else {
      showToast(d.error || 'Scheduling failed', 'error');
    }
  } catch (e) {
    showToast('Network error', 'error');
  }
}
