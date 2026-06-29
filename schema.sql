-- ============================================================
-- Pepper AI — Database Schema  v3.0
-- SQLite-compatible DDL (also works with PostgreSQL via Railway)
-- ============================================================
-- Usage:
--   sqlite3 instance/pepperai.db < schema.sql
--   OR: python -c "from app import app, db; app.app_context().push(); db.create_all()"
-- ============================================================

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ── Users ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id               INTEGER  PRIMARY KEY AUTOINCREMENT,
    google_id        TEXT     UNIQUE NOT NULL,
    email            TEXT     UNIQUE NOT NULL,
    name             TEXT,
    avatar           TEXT,
    -- Per-user YouTube OAuth tokens (NEVER shared between users)
    yt_access_token  TEXT,
    yt_refresh_token TEXT,
    yt_token_expiry  DATETIME,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login       DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_users_google_id ON users(google_id);
CREATE INDEX IF NOT EXISTS ix_users_email     ON users(email);

-- ── Channels ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS channels (
    id            INTEGER  PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    yt_channel_id TEXT,                        -- Google YouTube channel ID
    name          TEXT     NOT NULL,
    network       TEXT,                        -- ZEE / SUN / etc.
    language      TEXT,                        -- Hindi / Tamil / etc.
    genre         TEXT,                        -- Drama / Action / etc.
    description   TEXT,
    status        TEXT     NOT NULL DEFAULT 'ACTIVE',
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_channels_user_id      ON channels(user_id);
CREATE INDEX IF NOT EXISTS ix_channels_user_network ON channels(user_id, network);

-- ── Source Videos ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS source_videos (
    id                  INTEGER  PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename            TEXT     NOT NULL,
    original_name       TEXT,
    filepath            TEXT,
    file_size           INTEGER,
    -- Technical info (filled after ffprobe)
    duration            REAL,                   -- seconds
    resolution          TEXT,                   -- e.g. 1920x1080
    fps                 REAL,
    -- Content metadata
    network             TEXT,                   -- ZEE or SUN
    language            TEXT,
    genre               TEXT,
    content_type        TEXT,                   -- movie / episode / clip / promo
    title               TEXT,
    -- Pipeline state
    status              TEXT NOT NULL DEFAULT 'UPLOADED',
    -- UPLOADED → VALIDATED → PROCESSING → CLIPS_READY
    -- → METADATA_GENERATED → THUMBNAILS_GENERATED → QA_DONE
    -- → REVIEW_PENDING → PUBLISHED / ERROR
    processing_progress INTEGER DEFAULT 0,
    error_message       TEXT,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_sv_user_id      ON source_videos(user_id);
CREATE INDEX IF NOT EXISTS ix_sv_user_status  ON source_videos(user_id, status);
CREATE INDEX IF NOT EXISTS ix_sv_user_created ON source_videos(user_id, created_at);

-- ── Clips ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clips (
    id              INTEGER  PRIMARY KEY AUTOINCREMENT,
    source_video_id INTEGER  NOT NULL REFERENCES source_videos(id) ON DELETE CASCADE,
    channel_id      INTEGER  REFERENCES channels(id) ON DELETE SET NULL,
    user_id         INTEGER  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- File info
    filename        TEXT,
    filepath        TEXT,
    clip_type       TEXT,                       -- shorts | medium | longform | full
    duration        REAL,                       -- seconds
    start_time      REAL,                       -- position in source video
    end_time        REAL,
    resolution      TEXT,
    file_size       INTEGER,
    -- AI-Generated Metadata (Gemini 1.5 Flash)
    ai_title        TEXT,
    ai_description  TEXT,
    ai_tags         TEXT,                       -- JSON array
    ai_keywords     TEXT,                       -- JSON array
    -- Final metadata (after human review & editing)
    final_title       TEXT,
    final_description TEXT,
    final_tags        TEXT,                     -- JSON array
    -- Thumbnails
    thumbnail_path     TEXT,
    thumbnail_variants TEXT,                    -- JSON array of file paths
    selected_thumbnail INTEGER DEFAULT 0,
    -- QA Scores (100-point system; pass threshold = 55)
    qa_video_score     INTEGER DEFAULT 0,
    qa_metadata_score  INTEGER DEFAULT 0,
    qa_thumbnail_score INTEGER DEFAULT 0,
    qa_total_score     INTEGER DEFAULT 0,
    qa_passed          BOOLEAN DEFAULT FALSE,
    qa_notes           TEXT,
    -- Review
    status       TEXT NOT NULL DEFAULT 'CREATED',
    -- CREATED → METADATA_PENDING → METADATA_DONE → THUMBNAIL_DONE
    -- → QA_PASSED / QA_FAILED → REVIEW_PENDING
    -- → APPROVED → UPLOADING → PUBLISHED / REJECTED / SCHEDULED
    review_notes TEXT,
    -- YouTube publish info
    yt_video_id  TEXT,
    yt_url       TEXT,
    scheduled_at DATETIME,
    published_at DATETIME,
    yt_views     INTEGER DEFAULT 0,
    yt_likes     INTEGER DEFAULT 0,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_clips_user_id     ON clips(user_id);
CREATE INDEX IF NOT EXISTS ix_clips_sv_id       ON clips(source_video_id);
CREATE INDEX IF NOT EXISTS ix_clips_user_status ON clips(user_id, status);

-- ── Workflow Events (Audit Log) ───────────────────────────────
CREATE TABLE IF NOT EXISTS workflow_events (
    id              INTEGER  PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER  REFERENCES users(id) ON DELETE CASCADE,
    source_video_id INTEGER  REFERENCES source_videos(id) ON DELETE SET NULL,
    clip_id         INTEGER  REFERENCES clips(id) ON DELETE SET NULL,
    event_type      TEXT     NOT NULL,
    -- Common event types:
    -- LOGIN, LOGOUT, UPLOADED, VALIDATED, PROCESSING, SCENE_DETECTION,
    -- SCENES_DETECTED, EXTRACTING, CLIPS_READY, METADATA, METADATA_GENERATED,
    -- THUMBNAILS, THUMBNAILS_GENERATED, QA, QA_DONE, REVIEW_PENDING,
    -- APPROVED, REJECTED, SCHEDULED, YT_UPLOAD_STARTED, PUBLISHED,
    -- YT_ERROR, ERROR, CHANNEL_CREATED, VIDEO_DELETED, SECURITY_VIOLATION
    message         TEXT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_we_user_id      ON workflow_events(user_id);
CREATE INDEX IF NOT EXISTS ix_we_user_created ON workflow_events(user_id, created_at);
CREATE INDEX IF NOT EXISTS ix_we_sv_id        ON workflow_events(source_video_id);

-- ── End of schema ─────────────────────────────────────────────
