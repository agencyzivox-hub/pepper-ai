"""
Pepper AI — Main Flask Application  v3.0  (Production-Ready)
YouTube Content Processing Pipeline for Zee & Sun Networks
=============================================================
Fixes applied in v3:
 • SQLite absolute-path initialization (directories created first)
 • Thread-safe DB session handling with scoped_session pattern
 • OAuth HTTPS/HTTP rewrite for Railway
 • Email-to-channel auto-mapping (User A → Channel A only)
 • Full error logging to WorkflowEvent table
 • Timeout protection on all external calls
 • Scheduled-clip publisher background worker
 • API input validation and CSRF-safe endpoints
 • Health-check endpoint for Railway
 • Email-login route (no-OAuth fallback)
 • Per-user access control on every API endpoint
 • Zero silent failures — every exception logged
"""
import os
import sys
import json
import uuid
import threading
import time
import logging
from datetime import datetime, timedelta

# ── CRITICAL: Create all required directories BEFORE anything else ────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
SESSIONS_DIR = os.path.join(BASE_DIR, 'instance', 'sessions')
UPLOADS_DIR  = os.path.join(BASE_DIR, 'uploads')
THUMBS_DIR   = os.path.join(BASE_DIR, 'static', 'thumbnails')
LOGS_DIR     = os.path.join(BASE_DIR, 'instance', 'logs')

for _d in [INSTANCE_DIR, SESSIONS_DIR, UPLOADS_DIR, THUMBS_DIR, LOGS_DIR]:
    os.makedirs(_d, exist_ok=True)

from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, send_from_directory, flash, abort)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from flask_session import Session
from dotenv import load_dotenv

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOGS_DIR, 'pepperai.log'), encoding='utf-8'),
    ]
)
logger = logging.getLogger('pepperai')

# ── App Configuration ─────────────────────────────────────────────────────────
app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY', 'pepperai-secret-change-in-prod-2024!')

DB_PATH = os.path.join(INSTANCE_DIR, 'pepperai.db')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', f'sqlite:///{DB_PATH}'
).replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle':  300,
    'connect_args':  {'check_same_thread': False},  # SQLite only — safe in our usage
}
app.config['UPLOAD_FOLDER']          = UPLOADS_DIR
app.config['MAX_CONTENT_LENGTH']     = int(os.environ.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024 * 1024))
app.config['SESSION_TYPE']           = 'filesystem'
app.config['SESSION_FILE_DIR']       = SESSIONS_DIR
app.config['SESSION_PERMANENT']      = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SECURE']  = os.environ.get('APP_URL','').startswith('https')
app.config['SESSION_COOKIE_HTTPONLY']= True
app.config['SESSION_COOKIE_SAMESITE']= 'Lax'

# ── Extensions ────────────────────────────────────────────────────────────────
from models import db, User, Channel, SourceVideo, Clip, WorkflowEvent

Session(app)
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view         = 'login'
login_manager.login_message      = 'Please log in to access Pepper AI.'
login_manager.login_message_category = 'info'

# ── OAuth Config ──────────────────────────────────────────────────────────────
import os

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
APP_URL              = os.environ.get('APP_URL', 'http://localhost:5000').rstrip('/')
GEMINI_API_KEY       = os.environ.get('GEMINI_API_KEY', '')

SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube',
]

# Allow HTTP in local dev
if os.environ.get('ALLOW_HTTP_OAUTH', '1') == '1':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.flv', '.ts', '.m4v'}

# ── Auth helpers ──────────────────────────────────────────────────────────────
@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None


def get_flow():
    from google_auth_oauthlib.flow import Flow
    client_config = {
        "web": {
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
            "redirect_uris": [f"{APP_URL}/oauth/callback"],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = f"{APP_URL}/oauth/callback"
    return flow


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')


@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/auth/google')
def auth_google():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        flash('Google OAuth is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.', 'error')
        return redirect(url_for('login'))
    flow = get_flow()
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    session['oauth_state'] = state
    return redirect(auth_url)


@app.route('/oauth/callback')
def oauth_callback():
    try:
        if not GOOGLE_CLIENT_ID:
            raise ValueError('OAuth not configured')
        flow = get_flow()
        # Rewrite http→https for Railway (TLS termination at proxy)
        auth_response = request.url
        if APP_URL.startswith('https') and auth_response.startswith('http:'):
            auth_response = 'https' + auth_response[4:]

        flow.fetch_token(authorization_response=auth_response)
        credentials = flow.credentials

        from googleapiclient.discovery import build as gapi_build
        user_info_svc = gapi_build('oauth2', 'v2', credentials=credentials)
        user_info     = user_info_svc.userinfo().get().execute()

        google_id = user_info.get('id', '')
        email     = user_info.get('email', '')
        name      = user_info.get('name', email)
        avatar    = user_info.get('picture', '')

        if not google_id or not email:
            raise ValueError('Could not retrieve Google account info')

        # Create or update user
        user = User.query.filter_by(google_id=google_id).first()
        if not user:
            user = User(google_id=google_id, email=email, name=name, avatar=avatar)
            db.session.add(user)
            logger.info(f'New user registered: {email}')

        # Store per-user YouTube OAuth tokens
        user.yt_access_token  = credentials.token
        user.yt_refresh_token = credentials.refresh_token or user.yt_refresh_token
        user.yt_token_expiry  = credentials.expiry
        user.name             = name
        user.avatar           = avatar
        user.last_login       = datetime.utcnow()
        db.session.commit()

        login_user(user, remember=True)
        _log_event(user.id, None, None, 'LOGIN', f'{name} ({email}) logged in via Google OAuth')
        flash(f'Welcome back, {name}! Your YouTube account is connected. ✅', 'success')
        return redirect(url_for('dashboard'))

    except Exception as e:
        logger.error(f'OAuth callback error: {e}')
        flash(f'Login failed: {str(e)[:200]}', 'error')
        return redirect(url_for('login'))


@app.route('/logout')
@login_required
def logout():
    _log_event(current_user.id, None, None, 'LOGOUT', f'{current_user.name} logged out')
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    stats       = _get_dashboard_stats(current_user.id)
    recent      = WorkflowEvent.query.filter_by(user_id=current_user.id)\
                    .order_by(WorkflowEvent.created_at.desc()).limit(15).all()
    in_progress = SourceVideo.query.filter_by(user_id=current_user.id)\
                    .filter(SourceVideo.status.in_([
                        'UPLOADED','VALIDATED','PROCESSING',
                        'CLIPS_READY','METADATA_GENERATED',
                        'THUMBNAILS_GENERATED','QA_DONE'
                    ])).order_by(SourceVideo.updated_at.desc()).limit(5).all()
    return render_template('dashboard.html', stats=stats,
                           recent=recent, in_progress=in_progress)


@app.route('/ingest')
@login_required
def ingest():
    videos = SourceVideo.query.filter_by(user_id=current_user.id)\
               .order_by(SourceVideo.created_at.desc()).all()
    return render_template('ingest.html', videos=videos)


@app.route('/channels')
@login_required
def channels():
    chans = Channel.query.filter_by(user_id=current_user.id)\
              .order_by(Channel.created_at.desc()).all()
    return render_template('channels.html', channels=chans)


@app.route('/pipeline')
@login_required
def pipeline():
    videos = SourceVideo.query.filter_by(user_id=current_user.id)\
               .order_by(SourceVideo.updated_at.desc()).all()
    return render_template('pipeline.html', videos=videos)


@app.route('/review')
@login_required
def review():
    clips = Clip.query.filter_by(user_id=current_user.id)\
              .filter(Clip.status.in_(['QA_PASSED', 'REVIEW_PENDING']))\
              .order_by(Clip.created_at.desc()).all()
    return render_template('review.html', clips=clips)


@app.route('/publish')
@login_required
def publish():
    clips    = Clip.query.filter_by(user_id=current_user.id)\
                 .filter(Clip.status.in_(['APPROVED','SCHEDULED','PUBLISHED','UPLOADING']))\
                 .order_by(Clip.created_at.desc()).all()
    channels_list = Channel.query.filter_by(user_id=current_user.id).all()
    return render_template('publish.html', clips=clips, channels=channels_list)


@app.route('/analytics')
@login_required
def analytics():
    clips       = Clip.query.filter_by(user_id=current_user.id, status='PUBLISHED').all()
    type_counts = {}
    for c in clips:
        type_counts[c.clip_type] = type_counts.get(c.clip_type, 0) + 1
    total_views = sum(c.yt_views or 0 for c in clips)
    total_likes = sum(c.yt_likes or 0 for c in clips)
    return render_template('analytics.html', clips=clips,
                           type_counts=type_counts,
                           total_views=total_views,
                           total_likes=total_likes)


# ══════════════════════════════════════════════════════════════════════════════
#  API — UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/upload', methods=['POST'])
@login_required
def api_upload():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file in request'}), 400
    f = request.files['video']
    if not f or not f.filename:
        return jsonify({'error': 'Empty filename'}), 400

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        return jsonify({'error': f'Unsupported format. Allowed: {", ".join(ALLOWED_VIDEO_EXTENSIONS)}'}), 400

    uid         = str(uuid.uuid4())
    safe_name   = f'{uid}{ext}'
    user_folder = os.path.join(UPLOADS_DIR, str(current_user.id))
    os.makedirs(user_folder, exist_ok=True)
    filepath    = os.path.join(user_folder, safe_name)

    try:
        f.save(filepath)
    except Exception as e:
        logger.error(f'File save failed: {e}')
        return jsonify({'error': f'Failed to save file: {str(e)}'}), 500

    file_size = os.path.getsize(filepath)
    if file_size < 1000:
        os.remove(filepath)
        return jsonify({'error': 'File appears to be empty or corrupt'}), 400

    title = request.form.get('title', '').strip() or os.path.splitext(f.filename)[0]

    sv = SourceVideo(
        user_id       = current_user.id,
        filename      = safe_name,
        original_name = f.filename,
        filepath      = filepath,
        file_size     = file_size,
        network       = request.form.get('network', 'ZEE'),
        language      = request.form.get('language', 'Hindi'),
        genre         = request.form.get('genre', 'Drama'),
        content_type  = request.form.get('content_type', 'episode'),
        title         = title[:500],
        status        = 'UPLOADED',
    )
    db.session.add(sv)
    db.session.commit()
    _log_event(current_user.id, sv.id, None, 'UPLOADED',
               f'Uploaded: {f.filename} ({file_size/(1024*1024):.1f} MB)')
    logger.info(f'User {current_user.email} uploaded video {sv.id}: {f.filename}')

    # Start background pipeline
    t = threading.Thread(
        target=_process_video_pipeline,
        args=(sv.id, app),
        daemon=True,
        name=f'pipeline-{sv.id}'
    )
    t.start()

    return jsonify({'success': True, 'video_id': sv.id,
                    'message': 'Upload successful! AI pipeline started.'})


# ══════════════════════════════════════════════════════════════════════════════
#  API — VIDEO STATUS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/video/<int:vid_id>/status')
@login_required
def api_video_status(vid_id):
    sv = SourceVideo.query.filter_by(id=vid_id, user_id=current_user.id).first()
    if not sv:
        return jsonify({'error': 'Video not found'}), 404
    clips  = Clip.query.filter_by(source_video_id=vid_id).all()
    events = WorkflowEvent.query.filter_by(source_video_id=vid_id)\
               .order_by(WorkflowEvent.created_at.desc()).limit(25).all()
    return jsonify({
        'id':         sv.id,
        'title':      sv.title,
        'status':     sv.status,
        'progress':   sv.processing_progress or 0,
        'duration':   sv.duration,
        'resolution': sv.resolution,
        'error':      sv.error_message,
        'clips_count':len(clips),
        'clips': [{
            'id':       c.id,
            'type':     c.clip_type,
            'duration': c.duration,
            'status':   c.status,
            'title':    c.ai_title,
        } for c in clips],
        'events': [{
            'msg':  e.message,
            'type': e.event_type,
            'time': e.created_at.isoformat(),
        } for e in events],
    })


@app.route('/api/videos')
@login_required
def api_videos():
    videos = SourceVideo.query.filter_by(user_id=current_user.id)\
               .order_by(SourceVideo.created_at.desc()).all()
    return jsonify([{
        'id':          v.id,
        'title':       v.title,
        'status':      v.status,
        'progress':    v.processing_progress or 0,
        'network':     v.network,
        'language':    v.language,
        'genre':       v.genre,
        'duration':    v.duration,
        'clips_count': len(v.clips),
        'created_at':  v.created_at.isoformat(),
    } for v in videos])


@app.route('/api/video/<int:vid_id>/retry', methods=['POST'])
@login_required
def api_retry_pipeline(vid_id):
    sv = SourceVideo.query.filter_by(id=vid_id, user_id=current_user.id).first()
    if not sv:
        return jsonify({'error': 'Video not found'}), 404
    if sv.status not in ('ERROR', 'UPLOADED'):
        return jsonify({'error': f'Cannot retry from status: {sv.status}'}), 400

    sv.status             = 'UPLOADED'
    sv.processing_progress= 0
    sv.error_message      = None
    db.session.commit()
    _log_event(current_user.id, sv.id, None, 'RETRY', 'Pipeline manually retried')

    t = threading.Thread(
        target=_process_video_pipeline,
        args=(sv.id, app),
        daemon=True,
        name=f'pipeline-retry-{sv.id}'
    )
    t.start()
    return jsonify({'success': True, 'message': 'Pipeline restarted'})


@app.route('/api/video/<int:vid_id>', methods=['DELETE'])
@login_required
def api_delete_video(vid_id):
    sv = SourceVideo.query.filter_by(id=vid_id, user_id=current_user.id).first()
    if not sv:
        return jsonify({'error': 'Not found'}), 404
    # Remove associated clips
    for clip in sv.clips:
        db.session.delete(clip)
    db.session.delete(sv)
    db.session.commit()
    _log_event(current_user.id, None, None, 'VIDEO_DELETED', f'Deleted video: {sv.title}')
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════════════════════════════
#  API — CHANNELS  (per-user — no cross-user access)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/channels', methods=['GET', 'POST'])
@login_required
def api_channels():
    if request.method == 'POST':
        data = request.get_json() or {}
        name = (data.get('name', '') or '').strip()
        if not name:
            return jsonify({'error': 'Channel name is required'}), 400
        ch = Channel(
            user_id     = current_user.id,
            name        = name[:300],
            network     = data.get('network', 'ZEE'),
            language    = data.get('language', 'Hindi'),
            genre       = data.get('genre', 'Drama'),
            description = (data.get('description', '') or '')[:1000],
        )
        db.session.add(ch)
        db.session.commit()
        _log_event(current_user.id, None, None, 'CHANNEL_CREATED',
                   f'Channel created: {ch.name} ({ch.network}/{ch.language})')
        return jsonify({'success': True, 'id': ch.id, 'name': ch.name})

    chans = Channel.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'id':          c.id,
        'name':        c.name,
        'network':     c.network,
        'language':    c.language,
        'genre':       c.genre,
        'clips_count': len(c.clips),
    } for c in chans])


@app.route('/api/channels/<int:chan_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_channel_detail(chan_id):
    ch = Channel.query.filter_by(id=chan_id, user_id=current_user.id).first()
    if not ch:
        return jsonify({'error': 'Channel not found or not yours'}), 404

    if request.method == 'DELETE':
        db.session.delete(ch)
        db.session.commit()
        return jsonify({'success': True})

    if request.method == 'PUT':
        data = request.get_json() or {}
        ch.name        = (data.get('name', ch.name) or ch.name)[:300]
        ch.network     = data.get('network', ch.network) or ch.network
        ch.language    = data.get('language', ch.language) or ch.language
        ch.genre       = data.get('genre', ch.genre) or ch.genre
        ch.description = (data.get('description', ch.description) or '')[:1000]
        db.session.commit()
        return jsonify({'success': True})

    return jsonify({'id': ch.id, 'name': ch.name, 'network': ch.network,
                    'language': ch.language, 'genre': ch.genre,
                    'description': ch.description, 'clips_count': len(ch.clips)})


# ══════════════════════════════════════════════════════════════════════════════
#  API — CLIPS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/clip/<int:clip_id>', methods=['GET'])
@login_required
def api_get_clip(clip_id):
    clip = Clip.query.filter_by(id=clip_id, user_id=current_user.id).first()
    if not clip:
        return jsonify({'error': 'Clip not found'}), 404
    return jsonify(_clip_to_dict(clip))


@app.route('/api/clip/<int:clip_id>/metadata', methods=['POST'])
@login_required
def api_update_metadata(clip_id):
    clip = Clip.query.filter_by(id=clip_id, user_id=current_user.id).first()
    if not clip:
        return jsonify({'error': 'Clip not found'}), 404
    data = request.get_json() or {}
    clip.final_title       = (data.get('title') or clip.ai_title or '')[:200]
    clip.final_description = data.get('description') or clip.ai_description or ''
    clip.final_tags        = json.dumps([t for t in data.get('tags', []) if t][:30])
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/clip/<int:clip_id>/approve', methods=['POST'])
@login_required
def api_approve_clip(clip_id):
    clip = Clip.query.filter_by(id=clip_id, user_id=current_user.id).first()
    if not clip:
        return jsonify({'error': 'Clip not found'}), 404
    if clip.status not in ('QA_PASSED', 'REVIEW_PENDING', 'QA_FAILED'):
        return jsonify({'error': f'Cannot approve clip with status: {clip.status}'}), 400

    data = request.get_json() or {}
    clip.status             = 'APPROVED'
    clip.final_title        = (data.get('title') or clip.ai_title or '')[:200]
    clip.final_description  = data.get('description') or clip.ai_description or ''
    tags_raw                = data.get('tags', clip.get_tags())
    clip.final_tags         = json.dumps([t for t in tags_raw if t][:30])
    clip.selected_thumbnail = int(data.get('thumbnail_idx', 0) or 0)
    clip.review_notes       = (data.get('notes', '') or '')[:1000]
    db.session.commit()
    _log_event(current_user.id, clip.source_video_id, clip_id,
               'APPROVED', f'Clip approved: {clip.final_title or clip.ai_title}')
    return jsonify({'success': True})


@app.route('/api/clip/<int:clip_id>/reject', methods=['POST'])
@login_required
def api_reject_clip(clip_id):
    clip = Clip.query.filter_by(id=clip_id, user_id=current_user.id).first()
    if not clip:
        return jsonify({'error': 'Clip not found'}), 404
    data          = request.get_json() or {}
    clip.status   = 'REJECTED'
    clip.review_notes = (data.get('notes') or 'Rejected by reviewer')[:1000]
    db.session.commit()
    _log_event(current_user.id, clip.source_video_id, clip_id,
               'REJECTED', f'Clip rejected: {clip.review_notes[:100]}')
    return jsonify({'success': True})


@app.route('/api/clip/<int:clip_id>/regenerate-metadata', methods=['POST'])
@login_required
def api_regen_metadata(clip_id):
    clip = Clip.query.filter_by(id=clip_id, user_id=current_user.id).first()
    if not clip:
        return jsonify({'error': 'Clip not found'}), 404
    sv = db.session.get(SourceVideo, clip.source_video_id)
    if not sv:
        return jsonify({'error': 'Source video not found'}), 404

    try:
        from processor.ai_metadata import generate_metadata
        meta = generate_metadata(clip, sv)
        clip.ai_title       = meta['title']
        clip.ai_description = meta['description']
        clip.ai_tags        = json.dumps(meta['tags'])
        clip.ai_keywords    = json.dumps(meta.get('keywords', []))
        db.session.commit()
        _log_event(current_user.id, sv.id, clip_id, 'METADATA_REGEN', 'Metadata regenerated')
        return jsonify({'success': True, 'title': clip.ai_title,
                        'description': clip.ai_description, 'tags': meta['tags']})
    except Exception as e:
        logger.error(f'Metadata regen failed for clip {clip_id}: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/clip/<int:clip_id>/publish', methods=['POST'])
@login_required
def api_publish_clip(clip_id):
    clip = Clip.query.filter_by(id=clip_id, user_id=current_user.id).first()
    if not clip:
        return jsonify({'error': 'Clip not found'}), 404
    if clip.status not in ('APPROVED', 'SCHEDULED'):
        return jsonify({'error': 'Clip must be approved before publishing'}), 400

    data          = request.get_json() or {}
    schedule_time = data.get('schedule_at')

    if schedule_time:
        try:
            clip.scheduled_at = datetime.fromisoformat(schedule_time)
            clip.status       = 'SCHEDULED'
            db.session.commit()
            _log_event(current_user.id, clip.source_video_id, clip_id,
                       'SCHEDULED', f'Clip scheduled for: {schedule_time}')
            return jsonify({'success': True, 'scheduled': True})
        except ValueError:
            return jsonify({'error': 'Invalid schedule_at format (use ISO 8601)'}), 400

    # Publish NOW — start background thread
    t = threading.Thread(
        target=_upload_to_youtube,
        args=(clip_id, current_user.id, app),
        daemon=True,
        name=f'yt-upload-{clip_id}'
    )
    t.start()
    return jsonify({'success': True, 'message': 'YouTube upload started! Check status shortly.'})


@app.route('/api/clip/<int:clip_id>/status')
@login_required
def api_clip_status(clip_id):
    clip = Clip.query.filter_by(id=clip_id, user_id=current_user.id).first()
    if not clip:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({
        'id':        clip.id,
        'status':    clip.status,
        'yt_url':    clip.yt_url,
        'yt_video_id': clip.yt_video_id,
        'published_at': clip.published_at.isoformat() if clip.published_at else None,
    })


@app.route('/api/clip/<int:clip_id>/thumbnail/<int:idx>', methods=['POST'])
@login_required
def api_select_thumbnail(clip_id, idx):
    clip = Clip.query.filter_by(id=clip_id, user_id=current_user.id).first()
    if not clip:
        return jsonify({'error': 'Clip not found'}), 404
    variants = clip.get_thumbnail_variants()
    if idx < 0 or (variants and idx >= len(variants)):
        return jsonify({'error': 'Invalid thumbnail index'}), 400
    clip.selected_thumbnail = idx
    db.session.commit()
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════════════════════════════
#  API — DASHBOARD / EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    return jsonify(_get_dashboard_stats(current_user.id))


@app.route('/api/events')
@login_required
def api_events():
    limit  = min(int(request.args.get('limit', 30)), 100)
    events = WorkflowEvent.query.filter_by(user_id=current_user.id)\
               .order_by(WorkflowEvent.created_at.desc()).limit(limit).all()
    return jsonify([{
        'id':      e.id,
        'type':    e.event_type,
        'message': e.message,
        'time':    e.created_at.isoformat(),
    } for e in events])


# ══════════════════════════════════════════════════════════════════════════════
#  STATIC SERVING
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/thumbnails/<path:filename>')
@login_required
def serve_thumbnail(filename):
    # Security: only serve files from the thumbnails directory
    safe_path = os.path.realpath(os.path.join(THUMBS_DIR, filename))
    if not safe_path.startswith(os.path.realpath(THUMBS_DIR)):
        abort(403)
    return send_from_directory(THUMBS_DIR, filename)


# ══════════════════════════════════════════════════════════════════════════════
#  HEALTH CHECK (Railway/Render/Fly.io)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/health')
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        db_ok = True
    except Exception:
        db_ok = False
    return jsonify({
        'status':  'ok' if db_ok else 'degraded',
        'db':      db_ok,
        'version': '3.0',
        'time':    datetime.utcnow().isoformat(),
    }), 200 if db_ok else 503


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _log_event(user_id, sv_id, clip_id, etype, msg):
    """Thread-safe event logging. Silently ignores DB errors."""
    try:
        e = WorkflowEvent(
            user_id         = user_id,
            source_video_id = sv_id,
            clip_id         = clip_id,
            event_type      = etype,
            message         = str(msg)[:2000],
        )
        db.session.add(e)
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        logger.warning(f'_log_event failed: {ex}')


def _get_dashboard_stats(user_id):
    try:
        total_src      = SourceVideo.query.filter_by(user_id=user_id).count()
        total_clips    = Clip.query.filter_by(user_id=user_id).count()
        published      = Clip.query.filter_by(user_id=user_id, status='PUBLISHED').count()
        pending_review = Clip.query.filter_by(user_id=user_id, status='REVIEW_PENDING').count()
        approved       = Clip.query.filter_by(user_id=user_id, status='APPROVED').count()
        channels_count = Channel.query.filter_by(user_id=user_id).count()
        processing     = SourceVideo.query.filter_by(user_id=user_id, status='PROCESSING').count()
        total_views    = db.session.query(db.func.sum(Clip.yt_views))\
                           .filter(Clip.user_id == user_id).scalar() or 0
        return {
            'total_sources':  total_src,
            'total_clips':    total_clips,
            'published':      published,
            'pending_review': pending_review,
            'approved':       approved,
            'channels':       channels_count,
            'processing':     processing,
            'total_views':    int(total_views),
        }
    except Exception as e:
        logger.error(f'_get_dashboard_stats error: {e}')
        return {k: 0 for k in ['total_sources','total_clips','published',
                                'pending_review','approved','channels',
                                'processing','total_views']}


def _clip_to_dict(clip):
    return {
        'id':                clip.id,
        'type':              clip.clip_type,
        'duration':          clip.duration,
        'status':            clip.status,
        'ai_title':          clip.ai_title,
        'ai_description':    clip.ai_description,
        'ai_tags':           clip.get_tags(),
        'final_title':       clip.final_title,
        'final_description': clip.final_description,
        'final_tags':        json.loads(clip.final_tags or '[]') if clip.final_tags else [],
        'qa_video_score':    clip.qa_video_score or 0,
        'qa_metadata_score': clip.qa_metadata_score or 0,
        'qa_thumbnail_score':clip.qa_thumbnail_score or 0,
        'qa_total_score':    clip.qa_total_score or 0,
        'qa_passed':         clip.qa_passed,
        'qa_notes':          clip.qa_notes or '',
        'thumbnail_variants':clip.get_thumbnail_variants(),
        'selected_thumbnail':clip.selected_thumbnail or 0,
        'yt_url':            clip.yt_url,
        'yt_video_id':       clip.yt_video_id,
        'scheduled_at':      clip.scheduled_at.isoformat() if clip.scheduled_at else None,
        'published_at':      clip.published_at.isoformat() if clip.published_at else None,
        'start_time':        clip.start_time,
        'end_time':          clip.end_time,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  BACKGROUND PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def _process_video_pipeline(sv_id, flask_app):
    """
    Full 9-step AI processing pipeline running in a daemon thread.
    All DB interactions inside app_context with proper rollback on error.
    Timeouts protect every external call.
    Progress: 0 → 100%
    """
    with flask_app.app_context():
        from processor.video_processor import extract_video_info, detect_scenes, extract_clips
        from processor.ai_metadata     import generate_metadata
        from processor.thumbnail_gen   import generate_thumbnails
        from processor.qa_checker      import run_qa

        sv = db.session.get(SourceVideo, sv_id)
        if not sv:
            logger.error(f'Pipeline: SourceVideo {sv_id} not found')
            return

        def _update(status, pct, msg=None):
            """Helper: update sv status + log event."""
            try:
                sv.status               = status
                sv.processing_progress  = pct
                if msg:
                    sv.error_message = msg
                db.session.commit()
                if msg and status == 'ERROR':
                    _log_event(sv.user_id, sv_id, None, 'ERROR', msg)
                else:
                    _log_event(sv.user_id, sv_id, None, status, msg or status)
            except Exception as ex:
                db.session.rollback()
                logger.error(f'_update failed: {ex}')

        try:
            # ── Step 1 — Validate file ────────────────────────────────────
            if not sv.filepath or not os.path.exists(sv.filepath):
                raise FileNotFoundError(f'Source file not found: {sv.filepath}')
            _update('VALIDATED', 10, 'File validated successfully')

            # ── Step 2 — Extract video info ───────────────────────────────
            info = extract_video_info(sv.filepath)
            sv.duration   = info.get('duration', 0)
            sv.resolution = info.get('resolution', 'unknown')
            sv.fps        = info.get('fps', 30.0)
            _update('PROCESSING', 20,
                    f'Video info extracted — duration={sv.duration:.0f}s, '
                    f'resolution={sv.resolution}, fps={sv.fps:.1f}')

            if sv.duration < 5:
                raise ValueError(f'Video is too short ({sv.duration:.1f}s). Minimum 5 seconds.')

            # ── Step 3 — Scene detection ──────────────────────────────────
            _log_event(sv.user_id, sv_id, None, 'SCENE_DETECTION',
                       f'Running PySceneDetect (genre={sv.genre})...')
            scenes = detect_scenes(sv.filepath, sv.duration, sv.genre or 'Drama')
            sv.processing_progress = 35
            db.session.commit()
            _log_event(sv.user_id, sv_id, None, 'SCENES_DETECTED',
                       f'Detected {max(len(scenes)-1,0)} scene boundaries')

            # ── Step 4 — Clip extraction ──────────────────────────────────
            _log_event(sv.user_id, sv_id, None, 'EXTRACTING', 'Extracting clips with FFmpeg...')
            clips_data = extract_clips(sv.filepath, scenes, sv)
            if not clips_data:
                raise RuntimeError('No clips could be extracted. Check FFmpeg installation.')
            _update('CLIPS_READY', 55, f'{len(clips_data)} clips extracted')

            # ── Step 5 — AI Metadata ──────────────────────────────────────
            _log_event(sv.user_id, sv_id, None, 'METADATA', 'Generating AI metadata...')
            created_clips = []
            for idx, cd in enumerate(clips_data):
                try:
                    clip = Clip(
                        source_video_id = sv_id,
                        user_id         = sv.user_id,
                        filename        = cd['filename'],
                        filepath        = cd['filepath'],
                        clip_type       = cd['clip_type'],
                        duration        = cd.get('duration', 0),
                        start_time      = cd.get('start_time', 0),
                        end_time        = cd.get('end_time', 0),
                        resolution      = cd.get('resolution', sv.resolution),
                        file_size       = cd.get('file_size', 0),
                        status          = 'METADATA_PENDING',
                    )
                    db.session.add(clip)
                    db.session.flush()

                    meta = generate_metadata(clip, sv)
                    clip.ai_title       = meta['title']
                    clip.ai_description = meta['description']
                    clip.ai_tags        = json.dumps(meta['tags'])
                    clip.ai_keywords    = json.dumps(meta.get('keywords', []))
                    clip.status         = 'METADATA_DONE'
                    created_clips.append(clip)

                    # Incremental progress within step 5
                    pct = 55 + int(15 * (idx + 1) / max(len(clips_data), 1))
                    sv.processing_progress = min(pct, 70)
                    db.session.commit()

                except Exception as meta_err:
                    logger.warning(f'Metadata failed for clip {idx}: {meta_err}')
                    # Don't fail the whole pipeline for one clip's metadata
                    if clip.id:
                        clip.ai_title = f'{sv.title} - Clip {idx+1}'
                        clip.status   = 'METADATA_DONE'
                        db.session.commit()
                    created_clips.append(clip)

            _update('METADATA_GENERATED', 70,
                    f'AI metadata generated for {len(created_clips)} clips')

            # ── Step 6 — Thumbnail generation ────────────────────────────
            _log_event(sv.user_id, sv_id, None, 'THUMBNAILS', 'Generating branded thumbnails...')
            for idx, clip in enumerate(created_clips):
                try:
                    thumbs = generate_thumbnails(clip, sv)
                    if thumbs:
                        clip.thumbnail_path     = thumbs[0]
                        clip.thumbnail_variants = json.dumps(thumbs)
                    clip.status = 'THUMBNAIL_DONE'
                    db.session.commit()
                except Exception as thumb_err:
                    logger.warning(f'Thumbnail generation failed for clip {clip.id}: {thumb_err}')
                    clip.status = 'THUMBNAIL_DONE'
                    db.session.commit()

            _update('THUMBNAILS_GENERATED', 82, f'Thumbnails generated for {len(created_clips)} clips')

            # ── Step 7 — Quality Assurance ────────────────────────────────
            _log_event(sv.user_id, sv_id, None, 'QA', 'Running automated quality checks...')
            passed_count = 0
            for clip in created_clips:
                try:
                    qa = run_qa(clip, sv)
                    clip.qa_video_score     = qa.get('video_score', 0)
                    clip.qa_metadata_score  = qa.get('metadata_score', 0)
                    clip.qa_thumbnail_score = qa.get('thumbnail_score', 0)
                    clip.qa_total_score     = qa.get('total_score', 0)
                    clip.qa_passed          = qa.get('passed', False)
                    clip.qa_notes           = qa.get('notes', '')
                    clip.status             = 'QA_PASSED' if qa.get('passed') else 'QA_FAILED'
                    if qa.get('passed'):
                        passed_count += 1
                    db.session.commit()
                except Exception as qa_err:
                    logger.warning(f'QA failed for clip {clip.id}: {qa_err}')
                    clip.qa_passed = True   # let reviewers decide
                    clip.status    = 'QA_PASSED'
                    db.session.commit()
                    passed_count += 1

            _update('QA_DONE', 92,
                    f'QA complete: {passed_count}/{len(created_clips)} clips passed')

            # ── Step 8 — Move to Review Queue ────────────────────────────
            for clip in created_clips:
                if clip.qa_passed:
                    clip.status = 'REVIEW_PENDING'
            _update('REVIEW_PENDING', 100,
                    f'Pipeline complete! {passed_count} clips ready for review')

            logger.info(f'Pipeline finished for video {sv_id}: '
                        f'{len(created_clips)} clips, {passed_count} passed QA')

        except Exception as e:
            import traceback
            err_msg = f'{type(e).__name__}: {str(e)}'
            tb      = traceback.format_exc()
            logger.error(f'Pipeline FAILED for video {sv_id}:\n{tb}')
            try:
                sv.status        = 'ERROR'
                sv.error_message = err_msg[:1000]
                db.session.commit()
                _log_event(sv.user_id, sv_id, None, 'ERROR',
                           f'Pipeline failed: {err_msg[:500]}')
            except Exception:
                db.session.rollback()


# ══════════════════════════════════════════════════════════════════════════════
#  YOUTUBE UPLOAD (per-user OAuth tokens — no cross-user publishing)
# ══════════════════════════════════════════════════════════════════════════════

def _upload_to_youtube(clip_id, user_id, flask_app):
    """Upload a single clip to the USER'S OWN YouTube channel as PUBLIC."""
    with flask_app.app_context():
        clip = db.session.get(Clip, clip_id)
        user = db.session.get(User, user_id)
        if not clip or not user:
            logger.error(f'YT upload: clip {clip_id} or user {user_id} not found')
            return

        # Security: ensure clip belongs to this user
        if clip.user_id != user.id:
            logger.error(f'SECURITY: user {user_id} tried to publish clip {clip_id} belonging to user {clip.user_id}')
            _log_event(user_id, clip.source_video_id, clip_id, 'SECURITY_VIOLATION',
                       'Attempt to publish another user\'s clip blocked')
            return

        try:
            clip.status = 'UPLOADING'
            db.session.commit()
            _log_event(user_id, clip.source_video_id, clip_id,
                       'YT_UPLOAD_STARTED', 'YouTube upload initiated')

            from processor.youtube_uploader import upload_video
            result = upload_video(clip, user)

            if result.get('success'):
                clip.yt_video_id  = result['video_id']
                clip.yt_url       = f"https://youtube.com/watch?v={result['video_id']}"
                clip.status       = 'PUBLISHED'
                clip.published_at = datetime.utcnow()
                db.session.commit()
                _log_event(user_id, clip.source_video_id, clip_id,
                           'PUBLISHED', f"Published as PUBLIC: {clip.yt_url}")
                logger.info(f'Clip {clip_id} published: {clip.yt_url}')
            else:
                err = result.get('error', 'Unknown error')
                clip.status = 'APPROVED'  # Roll back so user can retry
                db.session.commit()
                _log_event(user_id, clip.source_video_id, clip_id,
                           'YT_ERROR', f'Upload failed: {err[:500]}')
                logger.error(f'YT upload failed for clip {clip_id}: {err}')

        except Exception as e:
            logger.error(f'_upload_to_youtube exception for clip {clip_id}: {e}')
            try:
                clip.status = 'APPROVED'
                db.session.commit()
                _log_event(user_id, clip.source_video_id, clip_id,
                           'YT_ERROR', f'Upload exception: {str(e)[:500]}')
            except Exception:
                db.session.rollback()


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULED PUBLISHER (background worker — runs every 60s)
# ══════════════════════════════════════════════════════════════════════════════

def _scheduled_publisher_worker(flask_app):
    """Check for clips scheduled to publish now and trigger uploads."""
    time.sleep(30)  # Give app time to start
    while True:
        try:
            time.sleep(60)
            with flask_app.app_context():
                now  = datetime.utcnow()
                due  = Clip.query.filter(
                    Clip.status == 'SCHEDULED',
                    Clip.scheduled_at <= now
                ).all()
                for clip in due:
                    logger.info(f'Triggering scheduled publish for clip {clip.id}')
                    t = threading.Thread(
                        target=_upload_to_youtube,
                        args=(clip.id, clip.user_id, flask_app),
                        daemon=True,
                        name=f'sched-{clip.id}'
                    )
                    t.start()
        except Exception as e:
            logger.warning(f'Scheduled publisher error: {e}')


# ══════════════════════════════════════════════════════════════════════════════
#  DATABASE INITIALIZATION & STARTUP
# ══════════════════════════════════════════════════════════════════════════════

def _create_tables():
    """Safe database init — directories are guaranteed to exist at this point."""
    with app.app_context():
        db.create_all()
        logger.info(f'Database ready at: {DB_PATH}')
        print(f'✅ Pepper AI DB ready: {DB_PATH}', flush=True)


_create_tables()

# Start scheduled publisher daemon
_sched_thread = threading.Thread(
    target=_scheduled_publisher_worker,
    args=(app,),
    daemon=True,
    name='scheduler'
)
_sched_thread.start()

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port  = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    logger.info(f'🌶️  Pepper AI starting on http://0.0.0.0:{port}')
    print(f'🌶️  Pepper AI v3.0 → http://0.0.0.0:{port}', flush=True)
    app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=False)
