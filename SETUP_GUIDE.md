# 🌶️ Pepper AI — Complete Setup Guide
## YouTube Content Processing Pipeline for Zee & Sun Networks

---

## ✅ What This System Does (Confirmed Features)

| Feature | Status | Detail |
|---|---|---|
| PySceneDetect scene detection | ✅ REAL | Genre-aware thresholds per content type |
| YouTube uploads as **PUBLIC** | ✅ CONFIRMED | `privacyStatus: 'public'` hardcoded |
| Gemini AI metadata | ✅ REAL | Gemini 1.5 Flash API |
| Branded thumbnails | ✅ REAL | Pillow + FFmpeg frame extraction |
| 10 language support | ✅ REAL | Tamil, Hindi, Telugu, Urdu, Malayalam, Odia, Kannada, Bengali, Marathi, English |
| Per-user YouTube channel | ✅ REAL | Each user's OAuth → their own channel |
| SQLite on live server | ✅ REAL | Absolute path DB, Railway volume mounted |
| Multi-device sync | ✅ REAL | Single SQLite DB on Railway volume |
| Anti-copy protection | ✅ ACTIVE | Right-click, Ctrl+U, F12, Ctrl+S disabled |
| Free lifetime (Railway) | ✅ POSSIBLE | Use Railway Hobby $5/mo or free tier |

---

## 📋 Prerequisites

Before you start, you need:
1. A **Google Cloud Console** account (free)
2. A **Railway** account (free at [railway.app](https://railway.app))
3. A **GitHub** account (free)
4. Your **Gemini API key** (already in the code)
5. Your **YouTube OAuth credentials** (already in the code)

---

## STEP 1: Google Cloud Console Setup

### 1.1 — Enable Required APIs
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (e.g., "Pepper AI")
3. In the left menu → **APIs & Services** → **Library**
4. Search and enable these APIs:
   - ✅ **YouTube Data API v3**
   - ✅ **Google+ API** (or People API)
   - ✅ **OAuth2 API**

### 1.2 — Configure OAuth Consent Screen
1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **External** (for all Google users)
3. Fill in:
   - App name: `Pepper AI`
   - User support email: your email
   - Developer contact: your email
4. Click **Save and Continue**
5. On **Scopes** page → click **Add or Remove Scopes**
6. Add these scopes:
   - `https://www.googleapis.com/auth/youtube.upload`
   - `https://www.googleapis.com/auth/youtube`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `https://www.googleapis.com/auth/userinfo.profile`
   - `openid`
7. Click **Save and Continue**
8. On **Test users** page → add your Gmail address
9. Click **Save and Continue** → **Back to Dashboard**

### 1.3 — Configure OAuth Credentials
1. Go to **APIs & Services** → **Credentials**
2. Click your existing OAuth 2.0 Client (or create new → **Web application**)
3. Under **Authorized redirect URIs**, add:
   ```
   http://localhost:5000/oauth/callback
   ```
   (We'll add the Railway URL in Step 4)
4. Click **Save**
5. Note your **Client ID** and **Client Secret** (already pre-configured in the code)

---

## STEP 2: Local Testing (Optional but Recommended)

### 2.1 — Install Python Dependencies
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2.2 — Install FFmpeg
```bash
# Ubuntu/Debian:
sudo apt-get install ffmpeg

# macOS:
brew install ffmpeg

# Windows:
# Download from https://ffmpeg.org/download.html
# Add to PATH
```

### 2.3 — Create .env file
```bash
cp .env.example .env
```
Edit `.env` and set:
```
SECRET_KEY=any-random-long-string-here-min-32-chars
APP_URL=http://localhost:5000
```

### 2.4 — Run Locally
```bash
python app.py
```
Open http://localhost:5000

### 2.5 — Test OAuth Login
1. Click "Sign in with Google"
2. Log in with a Google account that has a YouTube channel
3. Grant permissions
4. You should reach the Dashboard

---

## STEP 3: Railway Deployment

### 3.1 — Push Code to GitHub
```bash
cd /path/to/pepperai

# Initialize git (if not done)
git init
git add .
git commit -m "Initial Pepper AI deployment"

# Create GitHub repo and push
# Option A: GitHub CLI
gh repo create pepper-ai --private
git remote add origin https://github.com/YOUR_USERNAME/pepper-ai.git
git push -u origin main

# Option B: Manual
# Create repo at github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/pepper-ai.git
git push -u origin main
```

### 3.2 — Create Railway Project
1. Go to [railway.app](https://railway.app) → **New Project**
2. Select **Deploy from GitHub repo**
3. Connect your GitHub and select `pepper-ai`
4. Railway will detect `nixpacks.toml` automatically

### 3.3 — Add Persistent Volume (CRITICAL for SQLite)
1. In Railway project → Click **+ New** → **Volume**
2. Set:
   - **Mount Path**: `/home/user/pepperai/instance`
   - **Name**: `pepperai-db`
3. Click **Create**
4. Also add a second volume for uploads:
   - **Mount Path**: `/home/user/pepperai/uploads`
   - **Name**: `pepperai-uploads`

> ⚠️ **IMPORTANT**: Without persistent volumes, your SQLite database and uploads will be lost on every redeploy!

### 3.4 — Set Environment Variables
In Railway → Your service → **Variables** tab, add:

| Variable | Value |
|---|---|
| `SECRET_KEY` | `your-random-secret-key-min-32-chars` |
| `GOOGLE_CLIENT_ID` | `your_client_id_here` |
| `GOOGLE_CLIENT_SECRET` | `your_client_secret_here` |
| `GEMINI_API_KEY` | `your_key_here` |
| `APP_URL` | `https://YOUR-APP.up.railway.app` ← get from Railway settings |
| `ALLOW_HTTP_OAUTH` | `0` |
| `PORT` | `8080` |

> ⚠️ Set `APP_URL` AFTER you get your Railway URL (Step 3.5)

### 3.5 — Get Your Railway URL
1. In Railway → Your service → **Settings** → **Domains**
2. Click **Generate Domain** → you'll get something like `pepper-ai.up.railway.app`
3. Copy this URL and set `APP_URL=https://pepper-ai.up.railway.app`

---

## STEP 4: Final Google OAuth Configuration

### 4.1 — Add Railway URL to Google OAuth
1. Go back to [console.cloud.google.com](https://console.cloud.google.com)
2. **APIs & Services** → **Credentials** → your OAuth client
3. Under **Authorized redirect URIs**, add:
   ```
   https://YOUR-APP.up.railway.app/oauth/callback
   ```
4. Click **Save**

> ⏳ Google OAuth changes can take up to 5 minutes to propagate.

---

## STEP 5: Verify Deployment

### 5.1 — Check Railway Build Logs
In Railway → Your service → **Deployments** tab
- Look for: `✅ Database ready at: /home/user/pepperai/instance/pepperai.db`
- Look for: `Listening at: http://0.0.0.0:8080`

### 5.2 — Test the Application
1. Open `https://YOUR-APP.up.railway.app`
2. Click **Sign In with Google**
3. Log in and grant YouTube permissions
4. You should see the **Dashboard**

### 5.3 — Test Video Upload
1. Click **Ingest Content**
2. Upload a small test video (30-60 seconds)
3. Fill in: Network=ZEE, Language=Hindi, Genre=Drama
4. Click **Start Processing**
5. Watch the pipeline progress bar
6. After completion, go to **Review** to see your clips

### 5.4 — Test YouTube Publish
1. Go to **Review** → Approve a clip
2. Go to **Publish** → Click **Publish Now**
3. Video will upload to YOUR YouTube channel as PUBLIC
4. Check YouTube Studio to confirm

---

## 🌍 Multi-Device Sync

Since SQLite is stored on Railway's persistent volume:
- Multiple users can log in simultaneously
- Data persists across redeployments (volumes persist)
- All devices connecting to the same Railway URL share the same database
- No additional configuration needed!

---

## 🌐 10 Languages Supported

| Language | Script | YouTube Code |
|---|---|---|
| Hindi | देवनागरी | hi |
| Tamil | தமிழ் | ta |
| Telugu | తెలుగు | te |
| Urdu | اردو | ur |
| Malayalam | മലയാളം | ml |
| Odia | ଓଡ଼ିଆ | or |
| Kannada | ಕನ್ನಡ | kn |
| Bengali | বাংলা | bn |
| Marathi | मराठी | mr |
| English | English | en |

Each language gets:
- Language-specific CTA text (subscribe, watch)
- Language-specific keyword sets
- Correct YouTube `defaultLanguage` code
- Genre-specific metadata tuned for that language's content

---

## 🎬 PySceneDetect — How It Works

**Genre-specific thresholds** (lower = more sensitive):

| Genre | Threshold | Reason |
|---|---|---|
| Music | 20.0 | Music videos have rapid cuts |
| Action | 18.0 | Action has very fast cuts |
| Thriller | 22.0 | Thriller has quick scene changes |
| Comedy | 24.0 | Comedy varies in pacing |
| Drama | 28.0 | Drama has longer, slower scenes |
| Romance | 30.0 | Romance has very long scenes |
| Lifestyle | 32.0 | Talk shows are very slow-paced |

**Fallback chain:**
1. PySceneDetect AdaptiveDetector (most accurate)
2. FFmpeg `select=gt(scene,x)` filter
3. Interval-based segmentation (genre-tuned intervals)

---

## 📊 YouTube Upload Confirmation

Every video is uploaded with:
```python
'status': {
    'privacyStatus': 'public',      # ✅ PUBLIC — confirmed
    'selfDeclaredMadeForKids': False,
    'madeForKids': False,
}
```

**Shorts handling:**
- Vertical 9:16 format (1080x1920)
- `#Shorts` appended to title and description
- Duration kept 15-60 seconds

**Regular videos:**
- Horizontal 16:9 format (1920x1080)
- Full YouTube resumable upload API
- 10MB chunked upload (handles large files)
- Auto-retry on transient errors (HTTP 500/502/503)

---

## 🔒 Anti-Copy Protection

Disabled via JavaScript:
- ❌ Right-click (contextmenu)
- ❌ Ctrl+U (View Source)
- ❌ Ctrl+S (Save page)
- ❌ F12 (DevTools)
- ❌ Ctrl+Shift+I (DevTools)
- ❌ Ctrl+Shift+J (Console)
- ❌ Ctrl+Shift+C (Inspector)
- ❌ Ctrl+A (Select All — on page content)
- ❌ Ctrl+C / Ctrl+X (Copy/Cut — on page content)
- ❌ Text selection (on page content only)
- ❌ Image drag

✅ **Still works in form fields:**
- Ctrl+A, Ctrl+C, Ctrl+X, Ctrl+V all work in inputs and textareas

---

## 🚨 Troubleshooting

### "Login failed: redirect_uri_mismatch"
- Your `APP_URL` doesn't match what's in Google Cloud Console
- Fix: Add your exact URL to authorized redirect URIs in Google Console

### "No YouTube credentials"
- User's token expired or revoked
- Fix: Log out and log back in

### "Video file not found"
- Railway volume not mounted correctly
- Fix: Verify volume mount path is `/home/user/pepperai/uploads`

### "PySceneDetect not found"
- nixpacks didn't install it
- Fix: Check Railway build logs, ensure `requirements.txt` has `scenedetect[opencv]`

### "unable to open database file"
- Railway volume not mounted
- Fix: Add persistent volume at `/home/user/pepperai/instance`

### Thumbnail font issues
- DejaVu fonts not found
- Fix: Check `nixpacks.toml` has `dejavu_fonts` in nixPkgs

---

## 💰 Railway Pricing for Free/Low Cost

| Plan | Cost | What you get |
|---|---|---|
| Hobby | $5/month | 8GB RAM, 8 vCPU, 100GB storage |
| Free Trial | $5 credit | Enough to test everything |
| Pro | $20/month | More resources, teams |

For FFmpeg video processing, **Hobby plan ($5/mo) is recommended**.

---

## 📁 Project File Structure

```
pepperai/
├── app.py                    # Main Flask app (all routes, pipeline orchestration)
├── models.py                 # SQLAlchemy models (User, Channel, SourceVideo, Clip)
├── requirements.txt          # Python dependencies
├── nixpacks.toml             # Railway build config (FFmpeg, fonts, Python)
├── Procfile                  # Gunicorn startup command
├── railway.json              # Railway deployment config
├── .env.example              # Environment variables template
├── SETUP_GUIDE.md            # This file
│
├── processor/
│   ├── __init__.py
│   ├── video_processor.py    # PySceneDetect + FFmpeg clipping
│   ├── ai_metadata.py        # Gemini 1.5 Flash (10 languages)
│   ├── thumbnail_gen.py      # Pillow branded thumbnails
│   ├── qa_checker.py         # 100-point QA scoring
│   └── youtube_uploader.py   # YouTube Data API v3 (PUBLIC uploads)
│
├── templates/
│   ├── base.html             # Base layout + anti-copy protection
│   ├── landing.html          # Public landing page
│   ├── login.html            # Google OAuth login
│   ├── dashboard.html        # Main dashboard + KPIs
│   ├── ingest.html           # Video upload + pipeline progress
│   ├── channels.html         # YouTube channel management
│   ├── pipeline.html         # Processing pipeline monitor
│   ├── review.html           # Manual review queue
│   ├── publish.html          # YouTube publish + schedule
│   └── analytics.html        # Views/likes analytics
│
└── static/
    ├── css/style.css          # Dark theme design system
    └── js/
        ├── app.js             # Global utilities (toast, modal, API)
        ├── protect.js         # Anti-copy protection
        ├── ingest.js          # Upload + pipeline polling
        ├── review.js          # Review modal + approve/reject
        └── publish.js         # Publish + schedule tabs
```

---

## 🆘 Support

If you encounter issues:
1. Check Railway deployment logs first
2. Ensure all environment variables are set correctly
3. Verify Google OAuth redirect URIs match exactly
4. Make sure Railway volumes are mounted at the correct paths

---

*Pepper AI — Built for Zee & Sun Networks*
*Powered by: Google Gemini 1.5 Flash + PySceneDetect + FFmpeg + Pillow + YouTube Data API v3*
