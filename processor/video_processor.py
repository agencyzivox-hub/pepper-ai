"""
Pepper AI — Real Video Processor
Uses PySceneDetect for scene detection with genre-specific thresholds.
Falls back to interval-based segmentation if PySceneDetect fails.
"""
import os
import subprocess
import json
import uuid
import math
import logging

logger = logging.getLogger(__name__)

# ── Genre-specific scene detection thresholds ────────────────
# Lower threshold = more sensitive (detects more scene changes)
# Higher threshold = less sensitive (only detects big scene changes)
GENRE_THRESHOLDS = {
    'Action':    18.0,   # Action has rapid cuts — less sensitive
    'Thriller':  22.0,   # Thriller has quick cuts
    'Drama':     28.0,   # Drama has slower pacing — more sensitive
    'Romance':   30.0,   # Romance has long scenes
    'Comedy':    24.0,   # Comedy varies
    'Music':     20.0,   # Music videos cut fast
    'Lifestyle': 32.0,   # Talk shows / lifestyle are slow
    'News':      25.0,   # News has medium pacing
    'default':   27.0,
}

# ── Clip duration targets per type ───────────────────────────
CLIP_TARGETS = {
    'shorts':   {'min': 15,   'max': 60,   'target': 45},
    'medium':   {'min': 180,  'max': 300,  'target': 240},
    'longform': {'min': 600,  'max': 1800, 'target': 900},
}


def extract_video_info(filepath):
    """Get video metadata using ffprobe."""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_streams', '-show_format', filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(result.stderr[:300])
        data = json.loads(result.stdout)

        video_stream = next(
            (s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None
        )
        audio_stream = next(
            (s for s in data.get('streams', []) if s.get('codec_type') == 'audio'), None
        )

        duration = float(data.get('format', {}).get('duration', 0))
        width  = int(video_stream.get('width',  1920)) if video_stream else 1920
        height = int(video_stream.get('height', 1080)) if video_stream else 1080

        fps_str = (video_stream or {}).get('r_frame_rate', '30/1')
        try:
            num, den = fps_str.split('/')
            fps = float(num) / float(den)
        except Exception:
            fps = 30.0

        return {
            'duration':    duration,
            'resolution':  f'{width}x{height}',
            'fps':         round(fps, 2),
            'width':       width,
            'height':      height,
            'has_audio':   audio_stream is not None,
            'codec':       (video_stream or {}).get('codec_name', 'unknown'),
        }
    except Exception as e:
        logger.warning(f'extract_video_info failed: {e}')
        return {
            'duration': 0, 'resolution': '1920x1080',
            'fps': 30.0, 'width': 1920, 'height': 1080,
            'has_audio': True, 'codec': 'unknown',
            'error': str(e)
        }


def detect_scenes(filepath, duration, genre='Drama'):
    """
    Detect scene boundaries using PySceneDetect.
    Uses genre-specific threshold for smarter detection.
    Falls back to FFmpeg scene filter, then to interval splitting.
    """
    threshold = GENRE_THRESHOLDS.get(genre, GENRE_THRESHOLDS['default'])
    scenes = [0.0]

    # Method 1: PySceneDetect
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector, AdaptiveDetector

        video  = open_video(filepath)
        mgr    = SceneManager()

        # AdaptiveDetector works better for Indian TV content (variable lighting)
        mgr.add_detector(AdaptiveDetector(adaptive_threshold=threshold))

        # Limit how much we scan for very long videos (scan first 90 min)
        max_scan = min(duration, 5400)
        mgr.detect_scenes(video, end_time=max_scan, show_progress=False)
        scene_list = mgr.get_scene_list()

        for scene in scene_list:
            ts = scene[0].get_seconds()
            if 0 < ts < duration:
                scenes.append(round(ts, 2))

        logger.info(f'PySceneDetect found {len(scenes)-1} scenes (threshold={threshold}, genre={genre})')

    except Exception as e:
        logger.warning(f'PySceneDetect failed ({e}), trying FFmpeg fallback...')

        # Method 2: FFmpeg scene filter
        try:
            ff_threshold = threshold / 100.0  # FFmpeg uses 0.0–1.0
            cmd = [
                'ffmpeg', '-i', filepath,
                '-vf', f"select='gt(scene,{ff_threshold:.2f})',showinfo",
                '-f', 'null', '-', '-t', str(min(duration, 5400))
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            for line in result.stderr.split('\n'):
                if 'pts_time:' in line:
                    try:
                        ts = float(line.split('pts_time:')[1].split(' ')[0])
                        if 0 < ts < duration:
                            scenes.append(round(ts, 2))
                    except Exception:
                        pass
            logger.info(f'FFmpeg found {len(scenes)-1} scenes')
        except Exception as e2:
            logger.warning(f'FFmpeg scene detection also failed: {e2}')

    # Method 3: Interval fallback if not enough scenes
    if len(scenes) < 4 and duration > 60:
        logger.info('Using interval-based segmentation as fallback')
        # Adapt interval to genre:
        # Action/Music: shorter intervals, Drama/Lifestyle: longer
        intervals = {
            'Action': 60, 'Music': 45, 'Thriller': 75,
            'Drama': 120, 'Romance': 150, 'Lifestyle': 180,
        }
        interval = intervals.get(genre, 90)
        extra = [round(i * interval, 2) for i in range(1, int(duration / interval) + 1)]
        scenes.extend([t for t in extra if 0 < t < duration])

    scenes.append(duration)
    scenes = sorted(set(scenes))
    logger.info(f'Final scene count: {len(scenes)} for {duration:.0f}s video')
    return scenes


def extract_clips(filepath, scenes, source_video):
    """
    Extract clips from detected scenes.
    Creates: Shorts (15-60s), Medium (3-5min), Longform (10-30min)
    All clips encoded to H.264/AAC, optimized for YouTube.
    """
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'uploads', str(source_video.user_id), 'clips'
    )
    os.makedirs(output_dir, exist_ok=True)

    clips_data = []
    duration = source_video.duration or 0
    genre    = source_video.genre or 'Drama'

    if duration < 20:
        # Very short — treat as single short
        result = _extract_segment(filepath, 0, duration, 'shorts', output_dir, source_video)
        return result

    # ── Shorts (15-60s) ─── pick best segments across the video
    short_segs = _pick_segments(scenes, duration, 'shorts', genre)
    for seg in short_segs[:6]:
        clips_data.extend(_extract_segment(filepath, seg[0], seg[1], 'shorts', output_dir, source_video))

    # ── Medium (3-5 min) ─── only if video is long enough
    if duration > 200:
        medium_segs = _pick_segments(scenes, duration, 'medium', genre)
        for seg in medium_segs[:4]:
            clips_data.extend(_extract_segment(filepath, seg[0], seg[1], 'medium', output_dir, source_video))

    # ── Longform (10-30 min) ─── only for movies/episodes over 20 min
    if duration > 1200:
        long_segs = _pick_segments(scenes, duration, 'longform', genre)
        for seg in long_segs[:2]:
            clips_data.extend(_extract_segment(filepath, seg[0], seg[1], 'longform', output_dir, source_video))

    logger.info(f'Extracted {len(clips_data)} clips from {duration:.0f}s video')
    return clips_data


def _pick_segments(scenes, duration, clip_type, genre):
    """Pick segment start/end pairs for the given clip type."""
    cfg    = CLIP_TARGETS[clip_type]
    target = cfg['target']
    minlen = cfg['min']
    maxlen = cfg['max']
    segs   = []

    # Space segments evenly across video for variety
    step = max(1, len(scenes) // 8)
    i = 0
    while i < len(scenes) - 1:
        start = scenes[i]
        remaining = duration - start
        if remaining < minlen:
            i += 1
            continue
        seg_dur = min(target, remaining, maxlen)
        if seg_dur < minlen:
            i += 1
            continue
        end = start + seg_dur
        segs.append((start, end))
        # Jump ahead proportionally to avoid heavy overlap
        i += max(1, step)

    # Ensure we have at least one segment from the start and one from middle
    if not segs and duration >= minlen:
        segs.append((0, min(target, duration)))
        mid = duration / 2
        if mid + minlen <= duration:
            segs.append((mid, min(mid + target, duration)))

    return segs


def _extract_segment(filepath, start, end, clip_type, output_dir, sv):
    """Extract one clip using FFmpeg with YouTube-optimized encoding."""
    uid      = str(uuid.uuid4())[:8]
    filename = f"{clip_type}_{uid}.mp4"
    out_path = os.path.join(output_dir, filename)
    seg_dur  = end - start

    # ── Video filter based on clip type ─────────────────────
    if clip_type == 'shorts':
        # Vertical 9:16 for YouTube Shorts
        vf = (
            "scale='if(gt(iw/ih,9/16),trunc(ih*9/16/2)*2,iw)':"
            "'if(gt(iw/ih,9/16),ih,trunc(iw*16/9/2)*2)',"
            "pad=iw:ih:(ow-iw)/2:(oh-ih)/2,"
            "scale=1080:1920:flags=lanczos"
        )
        res = '1080x1920'
    else:
        # Horizontal 16:9 for regular YouTube
        vf = (
            "scale='if(gt(iw/ih,16/9),trunc(ih*16/9/2)*2,iw)':"
            "'if(gt(iw/ih,16/9),ih,trunc(iw*9/16/2)*2)',"
            "pad=iw:ih:(ow-iw)/2:(oh-ih)/2,"
            "scale=1920:1080:flags=lanczos"
        )
        res = '1920x1080'

    # ── FFmpeg command (YouTube-optimized) ───────────────────
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(round(start, 3)),
        '-i', filepath,
        '-t',  str(round(seg_dur, 3)),
        # Video
        '-vf', vf,
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '20',
        '-profile:v', 'high',
        '-level', '4.1',
        # Audio — normalize to YouTube standard -14 LUFS
        '-c:a', 'aac',
        '-b:a', '192k',
        '-ar', '48000',
        '-af', 'loudnorm=I=-14:TP=-1:LRA=11',
        # Container
        '-movflags', '+faststart',
        '-pix_fmt', 'yuv420p',
        out_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=900)
        if result.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            return [{
                'filename':   filename,
                'filepath':   out_path,
                'clip_type':  clip_type,
                'duration':   seg_dur,
                'start_time': start,
                'end_time':   end,
                'resolution': res,
                'file_size':  os.path.getsize(out_path),
            }]
        else:
            err = result.stderr[-500:] if result.stderr else 'Unknown error'
            logger.error(f'FFmpeg clip failed [{clip_type}] {start:.1f}–{end:.1f}s: {err}')
    except subprocess.TimeoutExpired:
        logger.error(f'FFmpeg timed out for clip {start:.1f}–{end:.1f}s')
    except Exception as e:
        logger.error(f'_extract_segment error: {e}')

    return []
