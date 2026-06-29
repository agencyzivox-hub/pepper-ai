"""
Pepper AI — Database Models  v3.0
SQLAlchemy models for all 5 tables with proper relations, indexes, and helpers.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login       import UserMixin
from datetime          import datetime
import json

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """Per-user account. YouTube OAuth tokens are stored here — never shared."""
    __tablename__ = 'users'

    id               = db.Column(db.Integer,     primary_key=True)
    google_id        = db.Column(db.String(200),  unique=True, nullable=False, index=True)
    email            = db.Column(db.String(200),  unique=True, nullable=False, index=True)
    name             = db.Column(db.String(200))
    avatar           = db.Column(db.String(500))
    # Per-user YouTube OAuth tokens (CRITICAL: user A tokens never used for user B)
    yt_access_token  = db.Column(db.Text)
    yt_refresh_token = db.Column(db.Text)
    yt_token_expiry  = db.Column(db.DateTime)
    # Timestamps
    created_at       = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login       = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    channels      = db.relationship('Channel',      backref='owner',        lazy='dynamic',
                                    cascade='all, delete-orphan')
    source_videos = db.relationship('SourceVideo',  backref='owner',        lazy='dynamic',
                                    cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.email}>'


class Channel(db.Model):
    """
    YouTube channel configuration per user.
    A user's clips are published ONLY to channels they own (user_id match enforced in app.py).
    """
    __tablename__ = 'channels'
    __table_args__ = (
        db.Index('ix_channels_user_network', 'user_id', 'network'),
    )

    id            = db.Column(db.Integer,    primary_key=True)
    user_id       = db.Column(db.Integer,    db.ForeignKey('users.id', ondelete='CASCADE'),
                               nullable=False, index=True)
    yt_channel_id = db.Column(db.String(200))          # Google YT channel ID (optional)
    name          = db.Column(db.String(300), nullable=False)
    network       = db.Column(db.String(50))            # ZEE, SUN, etc.
    language      = db.Column(db.String(50))            # Hindi, Tamil, etc.
    genre         = db.Column(db.String(50))            # Drama, Action, etc.
    description   = db.Column(db.Text)
    status        = db.Column(db.String(50), default='ACTIVE')
    created_at    = db.Column(db.DateTime,  default=datetime.utcnow, nullable=False)

    # Relationships
    clips = db.relationship('Clip', backref='channel', lazy='dynamic')

    def __repr__(self):
        return f'<Channel {self.name} ({self.network})>'


class SourceVideo(db.Model):
    """
    Uploaded source video — goes through the full pipeline.
    Status progression:
      UPLOADED → VALIDATED → PROCESSING → CLIPS_READY
      → METADATA_GENERATED → THUMBNAILS_GENERATED → QA_DONE
      → REVIEW_PENDING → [clips approved] → PUBLISHED / ERROR
    """
    __tablename__ = 'source_videos'
    __table_args__ = (
        db.Index('ix_sv_user_status', 'user_id', 'status'),
        db.Index('ix_sv_user_created', 'user_id', 'created_at'),
    )

    id                   = db.Column(db.Integer,    primary_key=True)
    user_id              = db.Column(db.Integer,    db.ForeignKey('users.id', ondelete='CASCADE'),
                                      nullable=False, index=True)
    filename             = db.Column(db.String(500), nullable=False)
    original_name        = db.Column(db.String(500))
    filepath             = db.Column(db.String(1000))
    file_size            = db.Column(db.BigInteger)
    # Video technical info (filled after ffprobe)
    duration             = db.Column(db.Float)          # seconds
    resolution           = db.Column(db.String(50))     # e.g. 1920x1080
    fps                  = db.Column(db.Float)
    # Content metadata
    network              = db.Column(db.String(50))     # ZEE / SUN
    language             = db.Column(db.String(50))     # Hindi, Tamil, etc.
    genre                = db.Column(db.String(50))     # Drama, Action, etc.
    content_type         = db.Column(db.String(50))     # movie, episode, clip, promo
    title                = db.Column(db.String(500))
    # Pipeline state
    status               = db.Column(db.String(50), default='UPLOADED', nullable=False)
    processing_progress  = db.Column(db.Integer,   default=0)
    error_message        = db.Column(db.Text)
    # Timestamps
    created_at           = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at           = db.Column(db.DateTime, default=datetime.utcnow,
                                      onupdate=datetime.utcnow)

    # Relationships
    clips = db.relationship('Clip', backref='source_video', lazy='dynamic',
                             cascade='all, delete-orphan')

    def __repr__(self):
        return f'<SourceVideo {self.title} [{self.status}]>'

    @property
    def clips_list(self):
        return list(self.clips)


class Clip(db.Model):
    """
    Individual extracted clip. Each clip goes through:
      METADATA_PENDING → METADATA_DONE → THUMBNAIL_DONE
      → QA_PASSED / QA_FAILED → REVIEW_PENDING
      → APPROVED → UPLOADING → PUBLISHED
      or → REJECTED / SCHEDULED
    """
    __tablename__ = 'clips'
    __table_args__ = (
        db.Index('ix_clips_user_status',   'user_id',   'status'),
        db.Index('ix_clips_sv_id',         'source_video_id'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    source_video_id = db.Column(db.Integer, db.ForeignKey('source_videos.id', ondelete='CASCADE'),
                                  nullable=False, index=True)
    channel_id      = db.Column(db.Integer, db.ForeignKey('channels.id',       ondelete='SET NULL'))
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id',          ondelete='CASCADE'),
                                  nullable=False, index=True)

    # File info
    filename    = db.Column(db.String(500))
    filepath    = db.Column(db.String(1000))
    clip_type   = db.Column(db.String(50))     # shorts | medium | longform | full
    duration    = db.Column(db.Float)           # seconds
    start_time  = db.Column(db.Float)           # position in source
    end_time    = db.Column(db.Float)
    resolution  = db.Column(db.String(50))
    file_size   = db.Column(db.BigInteger)

    # AI-Generated Metadata (Gemini 1.5 Flash)
    ai_title       = db.Column(db.String(200))
    ai_description = db.Column(db.Text)
    ai_tags        = db.Column(db.Text)         # JSON array
    ai_keywords    = db.Column(db.Text)         # JSON array

    # Final metadata (post-review edits)
    final_title       = db.Column(db.String(200))
    final_description = db.Column(db.Text)
    final_tags        = db.Column(db.Text)      # JSON array

    # Thumbnails
    thumbnail_path     = db.Column(db.String(1000))
    thumbnail_variants = db.Column(db.Text)     # JSON array of paths
    selected_thumbnail = db.Column(db.Integer,  default=0)

    # QA Scores (100-point system)
    qa_video_score     = db.Column(db.Integer, default=0)
    qa_metadata_score  = db.Column(db.Integer, default=0)
    qa_thumbnail_score = db.Column(db.Integer, default=0)
    qa_total_score     = db.Column(db.Integer, default=0)
    qa_passed          = db.Column(db.Boolean, default=False)
    qa_notes           = db.Column(db.Text)

    # Status
    status       = db.Column(db.String(50), default='CREATED', nullable=False)
    review_notes = db.Column(db.Text)

    # YouTube publish
    yt_video_id  = db.Column(db.String(200))
    yt_url       = db.Column(db.String(500))
    scheduled_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    yt_views     = db.Column(db.Integer, default=0)
    yt_likes     = db.Column(db.Integer, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_tags(self):
        """Return AI tags as Python list. Safe against corrupt JSON."""
        try:
            tags = json.loads(self.ai_tags or '[]')
            return tags if isinstance(tags, list) else []
        except Exception:
            return []

    def get_final_tags(self):
        try:
            tags = json.loads(self.final_tags or '[]')
            return tags if isinstance(tags, list) else []
        except Exception:
            return []

    def get_thumbnail_variants(self):
        """Return thumbnail path list. Safe against corrupt JSON."""
        try:
            variants = json.loads(self.thumbnail_variants or '[]')
            return variants if isinstance(variants, list) else []
        except Exception:
            return []

    def get_display_title(self):
        return self.final_title or self.ai_title or 'Untitled Clip'

    def __repr__(self):
        return f'<Clip {self.clip_type} [{self.status}] {self.duration:.0f}s>'


class WorkflowEvent(db.Model):
    """
    Audit log for every pipeline event, user action, error, and status change.
    Stored in DB so they survive across sessions and can be shown in UI.
    """
    __tablename__ = 'workflow_events'
    __table_args__ = (
        db.Index('ix_we_user_created',  'user_id', 'created_at'),
        db.Index('ix_we_sv_id',         'source_video_id'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id',          ondelete='CASCADE'),
                                  nullable=True, index=True)
    source_video_id = db.Column(db.Integer, db.ForeignKey('source_videos.id',  ondelete='SET NULL'),
                                  nullable=True)
    clip_id         = db.Column(db.Integer, db.ForeignKey('clips.id',          ondelete='SET NULL'),
                                  nullable=True)
    event_type      = db.Column(db.String(100), nullable=False)
    message         = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f'<WorkflowEvent {self.event_type}: {(self.message or "")[:50]}>'
