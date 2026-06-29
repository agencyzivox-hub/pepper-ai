# 🌶️ Pepper AI — YouTube Content Processing Pipeline  v3.0

**Production-ready AI pipeline for Zee & Sun networks — processes, clips, and publishes TV content to YouTube automatically.**

---

## ✅ Feature Matrix

| Feature | Status | Details |
|---------|--------|---------|
| Google OAuth Login | ✅ | Per-user YouTube token storage |
| Email-to-Channel Mapping | ✅ | User A → Channel A only (zero cross-user access) |
| Video Upload (up to 10GB) | ✅ | Drag-drop + browse, 6 formats supported |
| FFprobe Video Analysis | ✅ | Duration, resolution, FPS extraction |
| PySceneDetect v0.6.5 | ✅ | AdaptiveDetector + 9 genre-specific thresholds |
| 3-tier Scene Detection Fallback | ✅ | PySceneDetect → FFmpeg → Interval-based |
| FFmpeg Clip Extraction | ✅ | H.264/AAC, loudnorm -14 LUFS, YouTube-optimized |
| YouTube Shorts (vertical) | ✅ | 1080×1920, #Shorts tag, 15-60s |
| Medium Clips | ✅ | 1920×1080, 3-5 min |
| Long-form Clips | ✅ | 1920×1080, 10-30 min |
| Gemini 1.5 Flash AI Metadata | ✅ | Titles, descriptions, 28-30 tags |
| 10 Language Support | ✅ | Tamil, Hindi, Telugu, Urdu, Malayalam, Odia, Kannada, Bengali, Marathi, English |
| Real AI Thumbnails | ✅ | FFmpeg frames + Pillow branded overlays |
| Genre-specific Palettes | ✅ | 9 genres: Drama, Action, Comedy, Music, Romance, Thriller, Lifestyle, News |
| 100-point QA System | ✅ | Video + Metadata + Thumbnail + Content scoring |
| Review Queue | ✅ | Edit title/description/tags before publishing |
| YouTube Public Upload | ✅ | `privacyStatus: 'public'` — confirmed |
| Scheduled Publishing | ✅ | Background scheduler worker (checks every 60s) |
| Thumbnail Upload to YouTube | ✅ | Custom branded thumbnails uploaded with video |
| SQLite on Railway Volume | ✅ | Multi-device sync via persistent volume |
| Anti-copy Protection | ✅ | Ctrl+U, F12, right-click, all harmful keys disabled |
| Full Error Logging | ✅ | Every event stored in workflow_events table |
| Health Check Endpoint | ✅ | `/health` — used by Railway |
| Pipeline Retry | ✅ | One-click retry for failed videos |
| Per-user Access Control | ✅ | Zero cross-user data leakage |

---

## 🚀 Quick Start (Local)

```bash
# 1. Clone / unzip the project
cd pepperai

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install system dependencies
# Ubuntu/Debian:
sudo apt install ffmpeg
# macOS:
brew install ffmpeg

# 5. Configure environment
cp .env.example .env
# Edit .env with your Google OAuth credentials and Gemini API key

# 6. Run
python app.py
# → http://localhost:5000
```

---

## 🚀 Deploy to Railway

```bash
# 1. Push to GitHub
git init && git add . && git commit -m "Pepper AI v3"
gh repo create pepper-ai --public --push --source=.

# 2. On Railway.app:
#    → New Project → Deploy from GitHub → select repo

# 3. Add Volume (CRITICAL for SQLite persistence):
#    → New → Volume → Mount path: /home/user/pepperai/instance

# 4. Set Environment Variables (Settings → Variables):
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
APP_URL=https://your-app.up.railway.app
GEMINI_API_KEY=...
ALLOW_HTTP_OAUTH=0

# 5. Add OAuth callback URL in Google Cloud Console:
#    https://your-app.up.railway.app/oauth/callback
```

---

## 📁 Project Structure

```
pepperai/
├── app.py                      # Main Flask application (v3.0)
├── models.py                   # SQLAlchemy database models
├── requirements.txt            # Python dependencies
├── nixpacks.toml               # Railway build configuration
├── Procfile                    # Gunicorn startup command
├── railway.json                # Railway configuration
├── schema.sql                  # Database schema (reference)
├── .env.example                # Environment variables template
├── SETUP_GUIDE.md              # Step-by-step setup guide
├── DEPLOYMENT.md               # Deployment guide
├── README.md                   # This file
│
├── processor/                  # AI processing modules
│   ├── __init__.py
│   ├── video_processor.py      # PySceneDetect + FFmpeg clips
│   ├── ai_metadata.py          # Gemini 1.5 Flash + 10 languages
│   ├── thumbnail_gen.py        # FFmpeg frames + Pillow thumbnails
│   ├── qa_checker.py           # 100-point QA scoring
│   └── youtube_uploader.py     # PUBLIC YouTube upload
│
├── templates/                  # Jinja2 HTML templates
│   ├── base.html               # Layout + sidebar + anti-copy
│   ├── landing.html            # Public landing page
│   ├── login.html              # Google OAuth login
│   ├── dashboard.html          # KPI dashboard
│   ├── ingest.html             # Upload + drag-drop
│   ├── channels.html           # Channel management
│   ├── pipeline.html           # Processing status
│   ├── review.html             # Clip review + editing
│   ├── publish.html            # YouTube publishing
│   └── analytics.html          # Performance analytics
│
├── static/
│   ├── css/style.css           # Full dark theme (29KB)
│   └── js/
│       ├── app.js              # Global utilities
│       ├── ingest.js           # Upload + pipeline polling
│       ├── review.js           # Review modal
│       ├── publish.js          # Publishing + scheduling
│       └── protect.js          # Anti-copy protection
│
├── instance/                   # Created automatically
│   ├── pepperai.db             # SQLite database
│   ├── sessions/               # Flask-Session files
│   └── logs/pepperai.log       # Application logs
│
└── uploads/                    # Created automatically
    └── {user_id}/              # Per-user upload folders
        └── clips/              # Extracted clips
```

---

## 🔄 Pipeline Flow

```
User Login (Google OAuth)
    ↓
Channel Setup (email auto-linked to user's channels)
    ↓
Video Upload (MP4/MOV/MKV/AVI/WEBM, up to 10GB)
    ↓
Step 1: Validate (10%)  — file integrity check
Step 2: Extract Info (20%) — ffprobe: duration, resolution, FPS
Step 3: Scene Detection (35%) — PySceneDetect AdaptiveDetector
Step 4: Clip Extraction (55%) — FFmpeg H.264/AAC YouTube-optimized
Step 5: AI Metadata (70%) — Gemini 1.5 Flash, 10 languages
Step 6: Thumbnails (82%) — FFmpeg frames + Pillow branded overlays
Step 7: QA Scoring (92%) — 100-point automated quality check
Step 8: Review Queue (100%) — Human review + editing
    ↓
Approve → Schedule OR Publish Now
    ↓
YouTube Upload (PUBLIC, per-user OAuth, thumbnail included)
    ↓
Analytics Dashboard
```

---

## 🌍 Supported Languages

| Language | Script | Subscribe CTA |
|----------|--------|---------------|
| Hindi | हिन्दी | सब्सक्राइब करें |
| Tamil | தமிழ் | சந்தாக்கண்டு இருங்கள் |
| Telugu | తెలుగు | సబ్స్క్రైబ్ చేయండి |
| Urdu | اردو | سبسکرائب کریں |
| Malayalam | മലയാളം | സബ്സ്ക്രൈബ് ചെയ്യൂ |
| Odia | ଓଡ଼ିଆ | ସବ୍ସ୍କ୍ରାଇବ୍ କରନ୍ତୁ |
| Kannada | ಕನ್ನಡ | ಸಬ್‌ಸ್ಕ್ರೈಬ್ ಮಾಡಿ |
| Bengali | বাংলা | সাবস্ক্রাইব করুন |
| Marathi | मराठी | सबस्क्राइब करा |
| English | English | Subscribe |

---

## 🛡️ Security

- **Per-user OAuth tokens** — each user's YouTube credentials stored separately
- **Cross-user protection** — `/api/clip/{id}/publish` verifies `clip.user_id == logged_in_user.id`
- **Security logging** — violations logged to `workflow_events` with type `SECURITY_VIOLATION`
- **File type validation** — only `.mp4 .mov .mkv .avi .webm .flv .ts .m4v` accepted
- **Path traversal prevention** — thumbnail serving validates path is inside `THUMBS_DIR`
- **HTTPS enforcement** — `SESSION_COOKIE_SECURE=True` when APP_URL starts with `https`

---

## 🔧 API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload` | POST | Upload video + start pipeline |
| `/api/video/{id}/status` | GET | Get pipeline progress + events |
| `/api/video/{id}/retry` | POST | Retry failed pipeline |
| `/api/video/{id}` | DELETE | Delete video + clips |
| `/api/videos` | GET | List all user's videos |
| `/api/channels` | GET/POST | List/create channels |
| `/api/channels/{id}` | GET/PUT/DELETE | Channel CRUD |
| `/api/clip/{id}` | GET | Get clip details + metadata |
| `/api/clip/{id}/approve` | POST | Approve clip with edits |
| `/api/clip/{id}/reject` | POST | Reject clip |
| `/api/clip/{id}/publish` | POST | Publish or schedule |
| `/api/clip/{id}/status` | GET | Get clip publish status |
| `/api/clip/{id}/regenerate-metadata` | POST | Re-run Gemini AI |
| `/api/clip/{id}/thumbnail/{idx}` | POST | Select thumbnail variant |
| `/api/dashboard/stats` | GET | KPI counts |
| `/api/events` | GET | Recent activity log |
| `/health` | GET | Health check (DB ping) |

---

## 📊 Data Models

### Users
`id | google_id | email | name | avatar | yt_access_token | yt_refresh_token | yt_token_expiry | created_at | last_login`

### Channels
`id | user_id | yt_channel_id | name | network | language | genre | description | status | created_at`

### Source Videos
`id | user_id | filename | filepath | file_size | duration | resolution | fps | network | language | genre | content_type | title | status | processing_progress | error_message | created_at | updated_at`

### Clips
`id | source_video_id | channel_id | user_id | filename | filepath | clip_type | duration | start_time | end_time | resolution | file_size | ai_title | ai_description | ai_tags | final_title | final_description | final_tags | thumbnail_path | thumbnail_variants | selected_thumbnail | qa_*_score | qa_passed | qa_notes | status | review_notes | yt_video_id | yt_url | scheduled_at | published_at | yt_views | yt_likes | created_at | updated_at`

### Workflow Events
`id | user_id | source_video_id | clip_id | event_type | message | created_at`

---

## 📋 Requirements

- Python 3.10+
- FFmpeg 4.0+ (must be in PATH)
- 1GB+ RAM (for PySceneDetect)
- 10GB+ storage (for uploads + clips)

---

*Pepper AI v3.0 — Built for Zee & Sun Networks*
