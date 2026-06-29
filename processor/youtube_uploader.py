"""
Pepper AI — YouTube Uploader
Uploads clips to each user's OWN YouTube channel.
All videos are uploaded as PUBLIC by default.
"""
import os
import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

import os

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# YouTube video category IDs
CATEGORY_MAP = {
    'Drama':     '24',   # Entertainment
    'Action':    '1',    # Film & Animation
    'Comedy':    '23',   # Comedy
    'Music':     '10',   # Music
    'Thriller':  '24',   # Entertainment
    'Romance':   '24',   # Entertainment
    'News':      '25',   # News & Politics
    'Lifestyle': '22',   # People & Blogs
    'default':   '24',   # Entertainment
}

LANGUAGE_CODES = {
    'Hindi': 'hi', 'Tamil': 'ta', 'Telugu': 'te',
    'Kannada': 'kn', 'Malayalam': 'ml', 'Marathi': 'mr',
    'Bengali': 'bn', 'Odia': 'or', 'Urdu': 'ur', 'English': 'en',
}


def _abs_path(path):
    if not path:
        return None
    return os.path.abspath(path)


def _ensure_thumbnail_dirs():
    for rel_path in ('static/thumbnails', 'static/thumbnails/frames'):
        try:
            path = Path(rel_path).resolve()
            path.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning(f'Unable to ensure thumbnail directory {rel_path}: {exc}')


def _set_clip_status(clip, status):
    if not hasattr(clip, 'status'):
        return
    try:
        clip.status = status
        from models import db
        db.session.commit()
    except Exception as exc:
        logger.warning(
            f'Unable to update clip status to {status} for clip {getattr(clip, "id", "unknown")}: {exc}'
        )


def _set_clip_progress(clip, progress):
    if not hasattr(clip, 'upload_progress'):
        return
    try:
        clip.upload_progress = int(progress)
        from models import db
        db.session.commit()
    except Exception as exc:
        logger.warning(
            f'Unable to update upload progress for clip {getattr(clip, "id", "unknown")}: {exc}'
        )


def upload_video(clip, user):
    """
    Upload a clip to the user's own YouTube channel as PUBLIC.
    Uses their stored Google OAuth tokens.
    """
    _ensure_thumbnail_dirs()

    # ── Pre-flight checks ─────────────────────────────────────
    if not user.yt_access_token:
        _set_clip_status(clip, 'ERROR')
        return {
            'success': False,
            'error': 'No YouTube credentials found. Please log out and log back in to re-authorize.'
        }

    if not clip.filepath:
        _set_clip_status(clip, 'ERROR')
        return {'success': False, 'error': 'Clip file path is missing.'}

    filepath = _abs_path(clip.filepath)
    if not filepath or not os.path.exists(filepath):
        _set_clip_status(clip, 'ERROR')
        return {'success': False, 'error': f'Clip file not found: {filepath or clip.filepath}'}

    file_size = os.path.getsize(filepath)
    if file_size < 1000:
        _set_clip_status(clip, 'ERROR')
        return {'success': False, 'error': f'Clip file is too small ({file_size} bytes). Likely corrupt.'}

    _set_clip_status(clip, 'PROCESSING')
    logger.info(f'Uploading clip {clip.id} ({file_size / 1024 / 1024:.1f} MB) for user {user.id}')

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from googleapiclient.errors import HttpError

        # ── Build credentials from stored tokens ──────────────
        creds = Credentials(
            token         = user.yt_access_token,
            refresh_token = user.yt_refresh_token,
            token_uri     = 'https://oauth2.googleapis.com/token',
            client_id     = GOOGLE_CLIENT_ID,
            client_secret = GOOGLE_CLIENT_SECRET,
            scopes        = [
                'https://www.googleapis.com/auth/youtube.upload',
                'https://www.googleapis.com/auth/youtube',
            ]
        )

        # Auto-refresh if expired
        if creds.expired and creds.refresh_token:
            logger.info(f'Refreshing expired token for user {user.id}')
            creds.refresh(Request())
            from models import db
            user.yt_access_token = creds.token
            user.yt_token_expiry = creds.expiry
            db.session.commit()
            logger.info(f'Token refreshed for user {user.id}')

        youtube = build('youtube', 'v3', credentials=creds, cache_discovery=False)

        # ── Build metadata ────────────────────────────────────
        title       = (clip.final_title or clip.ai_title or 'Untitled Video')[:100]
        description = (clip.final_description or clip.ai_description or '')[:5000]

        try:
            tags = json.loads(clip.final_tags or clip.ai_tags or '[]')
        except Exception:
            tags = []

        # ── Load source video for genre/language ─────────────
        from models import SourceVideo

        sv = SourceVideo.query.get(clip.source_video_id)
        genre = sv.genre if sv else 'Drama'
        language = sv.language if sv else 'Hindi'
        category_id = CATEGORY_MAP.get(genre, CATEGORY_MAP['default'])
        lang_code = LANGUAGE_CODES.get(language, 'hi')

        # ── YouTube Shorts special handling ────────────────
        if clip.clip_type == 'shorts':
            if '#Shorts' not in title and len(title) < 95:
                title = title[:95] + ' #Shorts'

            if '#Shorts' not in description:
                description += '\n\n#Shorts #ShortVideo'

            if not tags:
                tags = []

            if 'Shorts' not in tags:
                tags = ['Shorts'] + tags

        # ── Clean tags ─────────────────────────────────────
        clean_tags = []

        for t in tags:
            if not t:
                continue

            t = str(t).strip()
            t = t.replace("#", "").replace(",", "")

            if len(t) > 30:
                t = t[:30]

            clean_tags.append(t)

        tags = clean_tags[:15]

        # ── Request body ───────────────────────────────────
        body = {
                'snippet': {
                'title':           title,
                'description':     description,
                'tags':            tags,
                'categoryId':      category_id,
                'defaultLanguage': lang_code,
            },
            'status': {
                'privacyStatus':            'public',
                'selfDeclaredMadeForKids':  False,
                'madeForKids':              False,
                'publishAt':                None,
            }
        }

        logger.info(f'Uploading clip {clip.id} as PUBLIC video: "{title}"')

        # ── Resumable upload with MediaFileUpload ─────────────
        media = MediaFileUpload(
            filepath,
            mimetype   = 'video/mp4',
            resumable  = True,
            chunksize  = 1024 * 1024 * 10
        )

        request = youtube.videos().insert(
            part       = 'snippet,status',
            body       = body,
            media_body = media
        )

        response    = None
        attempt     = 0
        max_retries = 5

        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    pct = int(status.progress() * 100)
                    logger.info(f'Upload progress: {pct}%')
                    _set_clip_progress(clip, pct)
            except HttpError as e:
                if e.resp.status in (500, 502, 503, 504) and attempt < max_retries:
                    wait = 2 ** attempt
                    logger.warning(f'YouTube API HTTP {e.resp.status}, retry {attempt+1} in {wait}s')
                    time.sleep(wait)
                    attempt += 1
                else:
                    raise

        video_id = response.get('id')
        if not video_id:
            _set_clip_status(clip, 'ERROR')
            return {'success': False, 'error': 'YouTube API returned no video ID.'}

        _set_clip_status(clip, 'UPLOADED')
        logger.info(f'✅ Clip {clip.id} uploaded as PUBLIC video: {video_id}')

        # ── Upload thumbnail ──────────────────────────────────
        thumb_variants = clip.get_thumbnail_variants()
        sel_idx        = clip.selected_thumbnail or 0
        thumb_uploaded = False

        if getattr(clip, 'thumbnails_generated', False):
            logger.info(f'Thumbnails already generated for clip {clip.id}; skipping thumbnail upload.')
        else:
            if thumb_variants and len(thumb_variants) > sel_idx:
                thumb_path = _abs_path(thumb_variants[sel_idx])
                if thumb_path and os.path.exists(thumb_path):
                    try:
                        from googleapiclient.http import MediaFileUpload as MFU
                        youtube.thumbnails().set(
                            videoId    = video_id,
                            media_body = MFU(thumb_path, mimetype='image/jpeg')
                        ).execute()
                        thumb_uploaded = True
                        logger.info(f'Thumbnail uploaded for video {video_id}')
                    except Exception as te:
                        logger.warning(f'Thumbnail upload failed (non-critical): {te}')

        if not thumb_uploaded:
            fallback_path = _abs_path('static/thumbnails/fallback.jpg')
            if fallback_path and os.path.exists(fallback_path):
                try:
                    from googleapiclient.http import MediaFileUpload as MFU
                    youtube.thumbnails().set(
                        videoId    = video_id,
                        media_body = MFU(fallback_path, mimetype='image/jpeg')
                    ).execute()
                    thumb_uploaded = True
                    logger.info(f'Fallback thumbnail uploaded for video {video_id}')
                except Exception as te:
                    logger.warning(f'Fallback thumbnail upload failed (non-critical): {te}')
            else:
                logger.warning(f'No thumbnail available for video {video_id}')

        if thumb_uploaded and hasattr(clip, 'thumbnails_generated'):
            try:
                clip.thumbnails_generated = True
                from models import db
                db.session.commit()
            except Exception as exc:
                logger.warning(f'Unable to persist thumbnail generation state for clip {clip.id}: {exc}')

        _set_clip_status(clip, 'THUMBNAILS_GENERATED')
        _set_clip_status(clip, 'DONE')
        _set_clip_progress(clip, 100)

        return {
            'success':  True,
            'video_id': video_id,
            'url':      f'https://youtube.com/watch?v={video_id}',
            'privacy':  'public',
        }

    except Exception as e:
        logger.error(f'YouTube upload failed for clip {clip.id}: {e}')
        _set_clip_status(clip, 'ERROR')
        return {'success': False, 'error': str(e)}


# ── Alias for backward compatibility ──────────────────────────
upload_to_youtube = upload_video
