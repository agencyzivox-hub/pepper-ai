/**
 * Pepper AI — Review Queue JavaScript
 */
'use strict';

let currentClipId = null;
let currentClipData = null;

async function openReview(clipId) {
  currentClipId = clipId;
  const body   = document.getElementById('reviewModalBody');
  const footer = document.getElementById('reviewModalFooter');
  if (!body) return;

  body.innerHTML = '<div class="loading-spinner"><i class="fas fa-spinner fa-spin"></i> Loading clip data...</div>';
  if (footer) footer.style.display = 'none';
  openModal('reviewModal');

  try {
    const r = await fetch(`/api/clip/${clipId}`);
    currentClipData = await r.json();
    renderReviewModal(currentClipData);
    if (footer) footer.style.display = 'flex';
  } catch (e) {
    body.innerHTML = `<div class="empty-state"><i class="fas fa-exclamation-triangle" style="color:var(--danger)"></i><p>Failed to load clip: ${e.message}</p></div>`;
  }
}

function renderReviewModal(d) {
  const body = document.getElementById('reviewModalBody');
  if (!body) return;

  const thumbs = d.thumbnail_variants || [];
  const tags   = d.ai_tags || [];
  const selThumb = d.selected_thumbnail || 0;

  const thumbsHtml = thumbs.length > 0
    ? thumbs.map((t, i) => `
        <div class="thumb-pick-item ${i === selThumb ? 'selected' : ''}"
             onclick="selectThumb(${d.id}, ${i}, this)"
             title="Variant ${i+1}">
         <img src="/static/thumbnails/${t.split('/').pop()}" />
               alt="Thumbnail ${i+1}"
               onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 9%22><rect fill=%22%231a1a26%22 width=%2216%22 height=%229%22/></svg>'"/>
        </div>`).join('')
    : '<span style="color:var(--text3);font-size:.82rem">No thumbnails generated</span>';

  const tagsFormatted = tags.join(', ');

  body.innerHTML = `
    <div class="review-video-side">
      <div style="background:var(--bg);border-radius:10px;aspect-ratio:16/9;display:flex;align-items:center;justify-content:center;color:var(--text3);font-size:1.5rem;border:1px solid var(--card-border)">
        <i class="fas fa-film"></i>
        <span style="font-size:.85rem;margin-left:10px">${formatDuration(d.duration)} · ${(d.type||'').toUpperCase()}</span>
      </div>

      <div class="card" style="padding:16px">
        <div style="font-size:.78rem;color:var(--text3);margin-bottom:8px;font-weight:600;text-transform:uppercase;letter-spacing:.5px">Thumbnails</div>
        <div class="review-thumb-picker">${thumbsHtml}</div>
      </div>

      <div class="card" style="padding:16px">
        <div style="font-size:.78rem;color:var(--text3);margin-bottom:10px;font-weight:600;text-transform:uppercase;letter-spacing:.5px">QA Score</div>
        <div class="qa-score-row">
          <div class="qa-score-bar" style="height:10px">
            <div class="qa-score-fill ${d.qa_total_score>=80?'qa-excellent':d.qa_total_score>=60?'qa-good':'qa-poor'}"
                 style="width:${d.qa_total_score||0}%;height:100%"></div>
          </div>
          <strong style="color:${d.qa_total_score>=80?'var(--success)':d.qa_total_score>=60?'var(--warning)':'var(--danger)'}">${d.qa_total_score||0}/100</strong>
        </div>
        ${d.qa_notes ? `<div style="font-size:.78rem;color:var(--text3);margin-top:8px;line-height:1.5">${d.qa_notes}</div>` : ''}
      </div>
    </div>

    <div class="review-meta-side">
      <div class="form-group">
        <label>Title <span style="color:var(--text3)">(max 100 chars)</span></label>
        <input type="text" id="reviewTitle" class="form-control"
               value="${escHtml(d.final_title || d.ai_title || '')}"
               maxlength="100"
               oninput="updateCharCount('reviewTitle','reviewTitleCount',100)"/>
        <div class="char-counter" id="reviewTitleCount"></div>
      </div>

      <div class="form-group">
        <label>Description <span style="color:var(--text3)">(200-400 words recommended)</span></label>
        <textarea id="reviewDesc" class="form-control" rows="8"
                  oninput="updateCharCount('reviewDesc','reviewDescCount',5000)">${escHtml(d.final_description || d.ai_description || '')}</textarea>
        <div class="char-counter" id="reviewDescCount"></div>
      </div>

      <div class="form-group">
        <label>Tags <span style="color:var(--text3)">(comma separated, max 30)</span></label>
        <textarea id="reviewTags" class="form-control" rows="3">${escHtml(tagsFormatted)}</textarea>
      </div>

      <div class="form-group">
        <label>Review Notes (optional)</label>
        <input type="text" id="reviewNotes" class="form-control" placeholder="Add notes for your team..."/>
      </div>
    </div>
  `;

  // Init char counters
  setTimeout(() => {
    updateCharCount('reviewTitle', 'reviewTitleCount', 100);
    updateCharCount('reviewDesc',  'reviewDescCount',  5000);
  }, 50);
}

function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function selectThumb(clipId, idx, el) {
  document.querySelectorAll('.thumb-pick-item').forEach(t => t.classList.remove('selected'));
  el.classList.add('selected');
  try {
    await fetch(`/api/clip/${clipId}/thumbnail/${idx}`, {method:'POST'});
    if (currentClipData) currentClipData.selected_thumbnail = idx;
  } catch (_) {}
}

async function submitApprove() {
  if (!currentClipId) return;
  const title = document.getElementById('reviewTitle')?.value.trim();
  if (!title) { showToast('Title is required', 'error'); return; }

  const tags = (document.getElementById('reviewTags')?.value || '')
    .split(',').map(t => t.trim()).filter(Boolean).slice(0, 30);

  const btn = document.getElementById('approveBtn');
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Approving...'; }

  try {
    const r = await fetch(`/api/clip/${currentClipId}/approve`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        title,
        description: document.getElementById('reviewDesc')?.value || '',
        tags,
        notes: document.getElementById('reviewNotes')?.value || '',
        thumbnail_idx: currentClipData?.selected_thumbnail || 0
      })
    });
    const d = await r.json();
    if (d.success) {
      showToast('✅ Clip approved! Moved to Publish queue.', 'success');
      closeModal('reviewModal');
      const card = document.querySelector(`[data-id="${currentClipId}"]`);
      if (card) { card.style.opacity='0'; card.style.transform='scale(.95)'; card.style.transition='all .3s'; setTimeout(()=>card.remove(),300); }
    } else {
      showToast(d.error || 'Approval failed', 'error');
      if (btn) { btn.disabled=false; btn.innerHTML='<i class="fas fa-check"></i> Approve & Move to Publish'; }
    }
  } catch (e) {
    showToast('Network error', 'error');
    if (btn) { btn.disabled=false; btn.innerHTML='<i class="fas fa-check"></i> Approve & Move to Publish'; }
  }
}

async function submitReject() {
  if (!currentClipId) return;
  const notes = document.getElementById('reviewNotes')?.value || 'Rejected during review';
  const btn = document.getElementById('rejectBtn');
  if (btn) { btn.disabled=true; btn.innerHTML='<i class="fas fa-spinner fa-spin"></i>'; }

  try {
    const r = await fetch(`/api/clip/${currentClipId}/reject`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({notes})
    });
    const d = await r.json();
    if (d.success) {
      showToast('Clip rejected', 'info');
      closeModal('reviewModal');
      const card = document.querySelector(`[data-id="${currentClipId}"]`);
      if (card) { card.style.opacity='0'; setTimeout(()=>card.remove(),300); }
    }
  } catch (e) { showToast('Error', 'error'); }
  if (btn) { btn.disabled=false; btn.innerHTML='<i class="fas fa-times"></i> Reject'; }
}

async function submitRegen() {
  if (!currentClipId) return;
  showToast('🤖 Regenerating AI metadata...', 'info');
  try {
    const r = await fetch(`/api/clip/${currentClipId}/regenerate-metadata`, {method:'POST'});
    const d = await r.json();
    if (d.success) {
      document.getElementById('reviewTitle').value = d.title || '';
      document.getElementById('reviewDesc').value  = d.description || '';
      document.getElementById('reviewTags').value  = (d.tags||[]).join(', ');
      showToast('✅ Metadata regenerated by Gemini AI!', 'success');
    } else {
      showToast(d.error || 'Regeneration failed', 'error');
    }
  } catch (e) { showToast('Network error', 'error'); }
}
