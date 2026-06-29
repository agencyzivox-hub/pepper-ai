"""
Pepper AI — Quality Assurance Checker
100-point automated QA system for clips before review.
"""
import os
import json
import logging

logger = logging.getLogger(__name__)


def run_qa(clip, source_video):
    """
    Run automated QA on a clip. Returns a dict with scores and pass/fail.
    Total score: 100 points
    - Video Quality:    30 pts
    - Metadata Quality: 30 pts
    - Thumbnail:        20 pts
    - Content Relevance:20 pts
    Pass threshold: 55+
    """
    notes = []

    # ── Video Quality (30 pts) ────────────────────────────────
    vq = _score_video_quality(clip, source_video, notes)

    # ── Metadata Quality (30 pts) ─────────────────────────────
    mq = _score_metadata(clip, source_video, notes)

    # ── Thumbnail (20 pts) ────────────────────────────────────
    tq = _score_thumbnail(clip, notes)

    # ── Content Relevance (20 pts) ────────────────────────────
    cq = _score_content_relevance(clip, source_video, notes)

    total = vq + mq + tq + cq
    passed = total >= 55

    if not notes:
        notes.append('All quality checks passed.')

    return {
        'video_score':     vq,
        'metadata_score':  mq,
        'thumbnail_score': tq,
        'content_score':   cq,
        'total_score':     total,
        'passed':          passed,
        'notes':           ' | '.join(notes),
    }


def _score_video_quality(clip, sv, notes):
    score = 0

    # File exists and readable
    if clip.filepath and os.path.exists(clip.filepath):
        score += 10
        size = os.path.getsize(clip.filepath)
        if size > 100_000:  # > 100KB — non-trivial
            score += 5
        else:
            notes.append('Video file is very small.')
    else:
        notes.append('Video file missing.')
        return 0

    # Duration check
    dur = clip.duration or 0
    if clip.clip_type == 'shorts':
        if 15 <= dur <= 60:
            score += 10
        elif dur < 15:
            notes.append(f'Short is too brief ({dur:.0f}s < 15s).')
            score += 3
        else:
            score += 6
    elif clip.clip_type == 'medium':
        if 120 <= dur <= 360:
            score += 10
        elif dur < 60:
            notes.append(f'Medium clip is too short ({dur:.0f}s).')
            score += 2
        else:
            score += 7
    elif clip.clip_type == 'longform':
        if 600 <= dur <= 1800:
            score += 10
        elif dur < 300:
            notes.append(f'Longform clip is too short ({dur:.0f}s).')
            score += 3
        else:
            score += 8
    else:
        score += 8

    # Resolution
    res = clip.resolution or ''
    if '1920' in res or '1080' in res:
        score += 5
    elif '1280' in res or '720' in res:
        score += 3
    elif res:
        score += 1
    else:
        notes.append('Resolution unknown.')

    return min(score, 30)


def _score_metadata(clip, sv, notes):
    score = 0

    # Title
    title = clip.ai_title or ''
    if title:
        tlen = len(title)
        if 30 <= tlen <= 100:
            score += 10
        elif tlen > 10:
            score += 6
            notes.append(f'Title length ({tlen}) not ideal (aim 30-100).')
        else:
            notes.append('Title is too short.')
            score += 2
        if sv.network.lower() in title.lower() or sv.language.lower() in title.lower():
            score += 3
    else:
        notes.append('AI title missing.')

    # Description
    desc = clip.ai_description or ''
    if desc:
        words = len(desc.split())
        if words >= 100:
            score += 10
        elif words >= 50:
            score += 6
            notes.append(f'Description is short ({words} words, aim 100+).')
        else:
            score += 3
            notes.append(f'Description too brief ({words} words).')
    else:
        notes.append('AI description missing.')

    # Tags
    try:
        tags = json.loads(clip.ai_tags or '[]')
    except Exception:
        tags = []
    if len(tags) >= 20:
        score += 7
    elif len(tags) >= 10:
        score += 4
    elif len(tags) > 0:
        score += 2
        notes.append(f'Only {len(tags)} tags (aim 20+).')
    else:
        notes.append('No tags generated.')

    return min(score, 30)


def _score_thumbnail(clip, notes):
    score = 0
    variants = clip.get_thumbnail_variants()
    if not variants:
        notes.append('No thumbnails generated.')
        return 0

    score += 8  # Has at least one thumbnail

    # Multiple variants
    if len(variants) >= 3:
        score += 6
    elif len(variants) >= 2:
        score += 3

    # Check file actually exists and has content
    real_thumbs = 0
    for t in variants:
        if t and os.path.exists(t) and os.path.getsize(t) > 5000:
            real_thumbs += 1

    if real_thumbs >= 3:
        score += 6
    elif real_thumbs >= 1:
        score += 3
        notes.append(f'Only {real_thumbs}/{len(variants)} thumbnails have content.')
    else:
        notes.append('Thumbnail files appear empty or missing.')

    return min(score, 20)


def _score_content_relevance(clip, sv, notes):
    score = 0

    # Network is set
    if sv.network:
        score += 5

    # Language is set and supported
    supported_langs = ['Hindi', 'Tamil', 'Telugu', 'Urdu', 'Malayalam',
                       'Odia', 'Kannada', 'Bengali', 'Marathi', 'English']
    if sv.language in supported_langs:
        score += 5
    elif sv.language:
        score += 2

    # Genre is set
    if sv.genre:
        score += 5

    # Content type is set
    if sv.content_type:
        score += 3

    # Title of source video is meaningful
    if sv.title and len(sv.title) > 3:
        score += 2

    return min(score, 20)

# ── Alias for backward compatibility ──────────────────────────
run_qa_checks = run_qa
