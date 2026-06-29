# 🚀 Pepper AI — Deployment Guide  v3.0

---

## Part 1 — Google Cloud Setup

### Step 1: Create Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click **New Project** → name it **"Pepper AI"**
3. Enable the following APIs (APIs & Services → Library):
   - **YouTube Data API v3**
   - **YouTube Analytics API v2**
   - **Google OAuth2 API**

### Step 2: Create OAuth 2.0 Credentials

1. APIs & Services → **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
2. Application type: **Web application**
3. Authorized redirect URIs:
   ```
   http://localhost:5000/oauth/callback         ← local dev
   https://your-app.up.railway.app/oauth/callback  ← production
   ```
4. Click **Create** → copy **Client ID** and **Client Secret**

### Step 3: Configure OAuth Consent Screen

1. APIs & Services → **OAuth consent screen**
2. User type: **External**
3. App name: **Pepper AI**
4. Add scopes:
   - `openid`
   - `userinfo.email`
   - `userinfo.profile`
   - `youtube.upload`
   - `youtube`
5. Add test users: your Google email(s)
6. Status: **Testing** (or publish for production)

### Step 4: Get Gemini API Key

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click **Create API Key**
3. Copy the key (starts with `AIzaSy...`)

---

## Part 2 — Local Development

### Prerequisites

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3 python3-pip python3-venv ffmpeg

# macOS
brew install python ffmpeg

# Windows
# Install Python 3.11 from python.org
# Install FFmpeg from https://ffmpeg.org/download.html
# Add ffmpeg to PATH
```

### Setup

```bash
# 1. Extract project
cd /path/to/pepperai

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate       # macOS/Linux
venv\Scripts\activate.bat      # Windows

# 3. Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configure .env
cp .env.example .env
nano .env  # or any text editor

# Fill in:
# SECRET_KEY=<random 64-char hex>
# GOOGLE_CLIENT_ID=...
# GOOGLE_CLIENT_SECRET=...
# APP_URL=http://localhost:5000
# GEMINI_API_KEY=...
# ALLOW_HTTP_OAUTH=1

# 5. Run
python app.py
```

Open [http://localhost:5000](http://localhost:5000)

---

## Part 3 — Railway Deployment

### Step 1: Prepare GitHub

```bash
cd pepperai
git init
git add .
git commit -m "Pepper AI v3.0 initial commit"

# Create GitHub repo (using GitHub CLI):
gh repo create pepper-ai --public --push --source=.

# OR manually on github.com → create repo → push
```

### Step 2: Deploy on Railway

1. Go to [railway.app](https://railway.app) → **New Project**
2. **Deploy from GitHub repo** → select your `pepper-ai` repo
3. Railway auto-detects nixpacks.toml → click **Deploy**

### Step 3: Add Persistent Volume (CRITICAL for SQLite)

1. In your Railway project → **+ New** → **Volume**
2. Select your service
3. **Mount path**: `/home/user/pepperai/instance`
4. Click **Add**

> ⚠️ Without this volume, your database resets on every deploy!

### Step 4: Set Environment Variables

In Railway → your service → **Variables** tab → **Add all**:

```env
SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_hex(32))">
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-secret
APP_URL=https://your-project.up.railway.app
GEMINI_API_KEY=AIzaSy-your-key
ALLOW_HTTP_OAUTH=0
```

### Step 5: Update Google OAuth Redirect URI

1. Back in [Google Cloud Console](https://console.cloud.google.com)
2. APIs & Services → Credentials → your OAuth client
3. Add to **Authorized redirect URIs**:
   ```
   https://your-project.up.railway.app/oauth/callback
   ```
4. Save

### Step 6: Verify Deployment

```bash
curl https://your-project.up.railway.app/health
# Expected: {"status": "ok", "db": true, "version": "3.0", ...}
```

---

## Part 4 — Multi-Device Sync

With the Railway volume mounted at `/home/user/pepperai/instance`:
- SQLite DB is stored on the persistent volume
- All devices accessing the Railway URL share the same database
- Sessions stored in filesystem (also on volume)
- Upload files stored locally — for true multi-server sync, migrate uploads to Railway's own object storage or S3

---

## Part 5 — Scaling Notes

### Current Architecture (Single Server)
- Suitable for: 1-5 concurrent users, up to 50 videos/day
- SQLite works well for this scale

### When to Scale
- **>5 concurrent users**: Switch DATABASE_URL to PostgreSQL (Railway offers managed Postgres)
- **>100 videos/day**: Add a task queue (Redis + Celery) for background processing
- **Multi-region**: Use Cloudflare R2 for video storage

### PostgreSQL Migration
```bash
# 1. Add Railway PostgreSQL
# Railway → New → Database → PostgreSQL
# Copy the DATABASE_URL

# 2. Set env var in Railway
DATABASE_URL=postgresql://user:pass@host:5432/railwaydb

# 3. The app auto-handles postgres:// → postgresql:// rewrite
```

---

## Part 6 — Troubleshooting

### "Login failed: redirect_uri_mismatch"
→ Your OAuth redirect URI in Google Cloud doesn't match APP_URL + `/oauth/callback`
→ Verify APP_URL env var has no trailing slash
→ Add exact URI to Google Cloud authorized list

### "Database ready" but routes crash
→ Check if Railway volume is mounted at the right path
→ Verify `ALLOW_HTTP_OAUTH=0` in production

### Pipeline stuck at 0%
→ FFmpeg not installed: check nixpacks.toml has `ffmpeg` in nixPkgs
→ Check logs: Railway → your service → **Logs** tab

### PySceneDetect import error
→ `scenedetect[opencv]` requires `libGL` — nixpacks.toml includes it
→ Try reinstalling: `pip install scenedetect[opencv]==0.6.5`

### YouTube upload fails: "No YouTube credentials"
→ User needs to re-login (OAuth tokens expired or not granted youtube.upload scope)
→ Click Logout → Login again to re-authorize

### Thumbnails not showing
→ Check `static/thumbnails/` directory exists and is writable
→ Ensure `THUMBS_DIR` is on the persistent volume if needed

---

## Part 7 — Security Hardening (Production)

```python
# In .env for production:
FLASK_DEBUG=0
ALLOW_HTTP_OAUTH=0
SECRET_KEY=<64-char random hex>

# Railway automatically:
# - Sets HTTPS for your domain
# - Provides TLS termination
# - Sets PORT environment variable
```

---

*Pepper AI Deployment Guide v3.0*
