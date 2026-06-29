"""
Pepper AI — Real AI Thumbnail Generator
Extracts best frames using FFmpeg + creates branded thumbnails using Pillow.
Genre-specific color schemes, network badges, gradient overlays, shadow text.
"""
import os
import uuid
import subprocess
import logging

logger = logging.getLogger(__name__)

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THUMB_DIR = os.path.join(BASE_DIR, 'static', 'thumbnails')

# ── Genre color palettes ──────────────────────────────────────
GENRE_PALETTES = {
    'Drama':     {'bg': (140, 10, 10),  'grad': (0, 0, 0),     'text': (255, 255, 255), 'accent': (255, 210, 0),  'badge_bg': (255, 30, 30)},
    'Action':    {'bg': (10, 10, 10),   'grad': (30, 0, 0),    'text': (255, 255, 255), 'accent': (255, 80, 0),   'badge_bg': (200, 30, 0)},
    'Comedy':    {'bg': (220, 160, 0),  'grad': (180, 80, 0),  'text': (20, 20, 20),   'accent': (255, 50, 50),  'badge_bg': (255, 180, 0)},
    'Music':     {'bg': (80, 0, 140),   'grad': (20, 0, 60),   'text': (255, 255, 255), 'accent': (255, 210, 0),  'badge_bg': (140, 0, 200)},
    'Romance':   {'bg': (160, 0, 70),   'grad': (60, 0, 30),   'text': (255, 255, 255), 'accent': (255, 180, 210),'badge_bg': (200, 0, 100)},
    'Thriller':  {'bg': (5, 5, 40),     'grad': (0, 0, 0),     'text': (255, 255, 255), 'accent': (0, 210, 255),  'badge_bg': (0, 100, 200)},
    'Lifestyle': {'bg': (0, 100, 60),   'grad': (0, 40, 20),   'text': (255, 255, 255), 'accent': (180, 255, 100),'badge_bg': (0, 150, 80)},
    'News':      {'bg': (10, 30, 80),   'grad': (0, 0, 30),    'text': (255, 255, 255), 'accent': (255, 210, 0),  'badge_bg': (200, 0, 0)},
    'default':   {'bg': (20, 20, 60),   'grad': (5, 5, 20),    'text': (255, 255, 255), 'accent': (255, 180, 0),  'badge_bg': (180, 30, 30)},
}

# ── Font paths (Railway nixpacks provides dejavu_fonts) ──────
FONT_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/dejavu-sans/DejaVuSans-Bold.ttf',
    '/nix/store/dejavu-fonts/share/fonts/truetype/DejaVuSans-Bold.ttf',
    # Fallback search path
]

FONT_PATH_REGULAR = [p.replace('-Bold', '') for p in FONT_PATHS]


def _find_font(bold=True):
    paths = FONT_PATHS if bold else FONT_PATH_REGULAR
    for p in paths:
        if os.path.exists(p):
            return p
    # Last resort: search in nix store
    try:
        result = subprocess.run(
            ['find', '/nix', '-name', 'DejaVuSans-Bold.ttf', '-type', 'f'],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().split('\n'):
            if line.strip() and os.path.exists(line.strip()):
                return line.strip()
    except Exception:
        pass
    return None


def generate_thumbnails(clip, source_video):
    """
    Generate 3 branded thumbnail variants for a clip.
    Returns list of thumbnail file paths.
    """
    os.makedirs(THUMB_DIR, exist_ok=True)
    os.makedirs(os.path.join(THUMB_DIR, 'frames'), exist_ok=True)

    thumbnails = []
    genre_value = str(source_video.genre or 'default').strip().title()
    palette     = GENRE_PALETTES.get(genre_value, GENRE_PALETTES['default'])
    title_text  = str(clip.ai_title or source_video.title or 'Watch Now')[:45]
    network     = str(source_video.network or 'ZEE')
    genre       = str(source_video.genre or 'Drama')

    # Extract multiple frames from different timestamps
    frames = _extract_best_frames(clip.filepath, clip.duration, clip.clip_type)
    if not frames:
        logger.debug('No frames extracted for clip %s', clip.id)

    # Generate 3 variants: genre-color, dark, light
    variants = [
        {'bg': palette['bg'],    'grad': palette['grad'],    'text': palette['text'],   'accent': palette['accent'],  'badge': palette['badge_bg']},
        {'bg': (8, 8, 16),       'grad': (0, 0, 0),          'text': (255, 255, 255),   'accent': palette['accent'],  'badge': palette['badge_bg']},
        {'bg': (245, 245, 255),  'grad': (200, 200, 220),    'text': (15, 15, 30),      'accent': palette['badge_bg'],'badge': palette['badge_bg']},
    ]

    for i, variant in enumerate(variants):
        frame = frames[i] if i < len(frames) else (frames[0] if frames else None)
        out = _create_thumbnail(frame, title_text, network, genre, variant, i)
        if out:
            thumbnails.append(out)

    logger.info(f'Generated {len(thumbnails)} thumbnails for clip {clip.id}')
    return thumbnails


def _extract_best_frames(filepath, duration, clip_type):
    """Extract 4 frames at key positions using FFmpeg."""
    frames = []
    if not filepath or not os.path.exists(filepath):
        return frames

    try:
        dur = float(duration or 30)
    except (TypeError, ValueError):
        dur = 30.0

    clip_type = str(clip_type or '').lower()
    if clip_type == 'shorts':
        timestamps = [dur * 0.15, dur * 0.4, dur * 0.65, dur * 0.85]
    else:
        timestamps = [dur * 0.1, dur * 0.3, dur * 0.55, dur * 0.75]

    for ts in timestamps:
        uid = str(uuid.uuid4())[:8]
        frame_path = os.path.join(THUMB_DIR, 'frames', f'frame_{uid}.jpg')
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(round(ts, 2)),
            '-i', filepath,
            '-vframes', '1',
            '-q:v', '1',          # highest quality
            '-s', '1280x720',
            '-vf', 'eq=brightness=0.05:saturation=1.2',  # slight enhancement
            frame_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and os.path.exists(frame_path) and os.path.getsize(frame_path) > 5000:
                frames.append(frame_path)
            else:
                if os.path.exists(frame_path):
                    try:
                        os.remove(frame_path)
                    except OSError:
                        pass
                logger.debug(
                    'FFmpeg failed at %s (returncode %s): %s',
                    round(ts, 2),
                    result.returncode,
                    (result.stderr or result.stdout or '').strip()
                )
        except subprocess.TimeoutExpired as e:
            if os.path.exists(frame_path):
                try:
                    os.remove(frame_path)
                except OSError:
                    pass
            logger.debug('FFmpeg timeout at %s: %s', round(ts, 2), e)
        except Exception as e:
            if os.path.exists(frame_path):
                try:
                    os.remove(frame_path)
                except OSError:
                    pass
            logger.debug('Frame extraction failed at %s: %s', round(ts, 2), e)

    return frames


def _create_thumbnail(frame_path, title, network, genre, variant, idx):
    """Create a single branded 1280x720 thumbnail."""
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageEnhance

        uid = str(uuid.uuid4())[:8]
        out_path = os.path.join(THUMB_DIR, f'thumb_{uid}_v{idx}.jpg')
        W, H = 1280, 720  # YouTube recommended thumbnail size

        img = None
        if frame_path and os.path.exists(frame_path):
            try:
                img = Image.open(frame_path).convert('RGB')
                img = img.resize((W, H), Image.LANCZOS)
                img = ImageEnhance.Contrast(img).enhance(1.25)
                img = ImageEnhance.Color(img).enhance(1.3)
                img = ImageEnhance.Brightness(img).enhance(1.08)
            except Exception as e:
                logger.debug('Failed to open frame %s: %s', frame_path, e)
                img = None

        if img is None:
            img = _gradient_bg(W, H, variant['bg'], variant['grad'])

        img = img.convert('RGBA')
        overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        for y in range(H // 2, H):
            alpha = int(220 * ((y - H // 2) / float(H // 2)) ** 1.4)
            alpha = min(alpha, 220)
            r, g, b = variant['bg']
            ov_draw.line([(0, y), (W, y)], fill=(r, g, b, alpha))

        img = Image.alpha_composite(img, overlay).convert('RGB')
        draw = ImageDraw.Draw(img)

        # ── Accent bar at bottom ──────────────────────────────
        bar_h = 12
        draw.rectangle([(0, H - bar_h), (W, H)], fill=variant['accent'])

        # ── Top-right network badge ───────────────────────────
        _draw_network_badge(draw, network, W, variant)

        # ── Genre pill (top-left) ─────────────────────────────
        _draw_genre_pill(draw, genre, variant)

        # ── Title text (bottom area) ──────────────────────────
        _draw_title(draw, title, W, H, variant)

        # ── Play button icon ──────────────────────────────────
        _draw_play_icon(draw, W, H, variant)

        img.save(out_path, 'JPEG', quality=92, optimize=True)
        return out_path

    except Exception as e:
        logger.error(f'Thumbnail creation failed: {e}')
        return _plain_fallback(title, network, variant, idx)


def _gradient_bg(w, h, color1, color2):
    """Create a smooth gradient background."""
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (w, h), color1)
    draw = ImageDraw.Draw(img)
    if h <= 1:
        return img
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    step = float(max(h - 1, 1))
    for y in range(h):
        t = y / step
        draw.line(
            [(0, y), (w, y)],
            fill=(
                int(r1 + (r2 - r1) * t),
                int(g1 + (g2 - g1) * t),
                int(b1 + (b2 - b1) * t)
            )
        )
    return img


def _get_font(size, bold=True):
    """Load a font, fall back to default if unavailable."""
    from PIL import ImageFont
    path = _find_font(bold)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)


def _text_bbox(draw, text, font):
    if hasattr(draw, 'textbbox'):
        return draw.textbbox((0, 0), text, font=font)
    w, h = draw.textsize(text, font=font)
    return (0, 0, w, h)


def _draw_network_badge(draw, network, W, variant):
    """Draw network name badge top-right."""
    from PIL import ImageFont
    font = _get_font(22, bold=True)
    text = str(network or '').upper()
    bbox = _text_bbox(draw, text, font)
    tw = bbox[2] - bbox[0]
    pad_x = 18
    bw, bh = tw + pad_x * 2, 40
    bx, by = W - bw - 16, 16
    draw.rectangle([(bx, by), (bx + bw, by + bh)], fill=variant['badge'])
    draw.rectangle([(bx, by), (bx + bw, by + bh)], outline=(255, 255, 255), width=2)
    tx = bx + (bw - tw) // 2
    ty = by + (bh - (bbox[3] - bbox[1])) // 2
    draw.text((tx + 1, ty + 1), text, font=font, fill=(0, 0, 0))
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255))


def _draw_genre_pill(draw, genre, variant):
    """Draw genre pill top-left."""
    from PIL import ImageFont
    font = _get_font(18, bold=True)
    text = str(genre or 'Drama').upper()
    bbox = _text_bbox(draw, text, font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = 14, 8
    bx, by = 16, 16
    bw = tw + px * 2
    bh = th + py * 2
    ac = variant['accent']
    draw.rectangle([(bx, by), (bx + bw, by + bh)], fill=(ac[0], ac[1], ac[2]))
    draw.text((bx + px, by + py), text, font=font, fill=(15, 15, 15))


def _draw_title(draw, title, W, H, variant):
    """Draw wrapped title text in the lower portion."""
    from PIL import ImageFont
    font_lg = _get_font(52, bold=True)
    font_sm = _get_font(38, bold=True)

    title = str(title or '')[:60]
    words = title.split()
    max_w = W - 60
    lines = []
    current = ''

    for word in words:
        test = (current + ' ' + word).strip()
        bbox = _text_bbox(draw, test, font_lg)
        if bbox[2] - bbox[0] <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    if len(lines) > 2:
        lines, current = [], ''
        for word in words:
            test = (current + ' ' + word).strip()
            bbox = _text_bbox(draw, test, font_sm)
            if bbox[2] - bbox[0] <= max_w:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        font_use = font_sm
        line_h = 46
    else:
        font_use = font_lg
        line_h = 62

    start_y = H - 30 - len(lines) * line_h - 20

    for i, line in enumerate(lines[:3]):
        y = start_y + i * line_h
        x = 30
        draw.text((x + 2, y + 2), line, font=font_use, fill=(0, 0, 0))
        draw.text((x, y), line, font=font_use, fill=variant['text'])


def _draw_play_icon(draw, W, H, variant):
    """Draw a subtle play button in the center-right area."""
    cx, cy = W - 120, H // 2 - 30
    r = 32
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(10, 10, 10))
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=(255, 255, 255), width=2)
    offset = 4
    pts = [(cx - 10 + offset, cy - 16), (cx - 10 + offset, cy + 16), (cx + 18 + offset, cy)]
    draw.polygon(pts, fill=(255, 255, 255))


def _plain_fallback(title, network, variant, idx):
    """Simplest possible fallback thumbnail."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        uid  = str(uuid.uuid4())[:8]
        path = os.path.join(THUMB_DIR, f'thumb_{uid}_fb{idx}.jpg')
        img  = Image.new('RGB', (1280, 720), variant['bg'])
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, 0), (1280, 12)], fill=variant['accent'])
        draw.rectangle([(0, 708), (1280, 720)], fill=variant['accent'])
        text_network = str(network or '')
        text_title   = str(title or '')[:50]
        font = _get_font(72, bold=True)
        draw.text((80, 200), text_network, font=font, fill=variant['accent'])
        font2 = _get_font(44, bold=False)
        draw.text((80, 320), text_title, font=font2, fill=variant['text'])
        img.save(path, 'JPEG', quality=85)
        return path
    except Exception:
        return None
