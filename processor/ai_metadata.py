"""
Pepper AI — AI Metadata Generator
Uses Google Gemini 1.5 Flash for SEO-optimized metadata in 10 languages.
Supports: Tamil, Hindi, Telugu, Urdu, Malayalam, Odia, Kannada, Bengali, Marathi, English
"""
import os
import json
import re
import logging

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ── Language metadata ─────────────────────────────────────────
LANG_CONFIG = {
    'Tamil': {
        'code': 'ta', 'youtube_code': 'ta',
        'subscribe_cta': 'சந்தாக்கண்டு இருங்கள்',
        'watch_cta': 'இந்த வீடியோவை பாருங்கள்',
        'keywords_extra': ['Tamil serial', 'Tamil TV', 'Tamil entertainment', 'Kollywood',
                           'Sun TV Tamil', 'Zee Tamil', 'Tamil drama', 'Tamil movies'],
    },
    'Hindi': {
        'code': 'hi', 'youtube_code': 'hi',
        'subscribe_cta': 'सब्सक्राइब करें',
        'watch_cta': 'यह वीडियो देखें',
        'keywords_extra': ['Hindi serial', 'Bollywood', 'Star Plus', 'Colors TV',
                           'Zee TV Hindi', 'Sony TV', 'Hindi drama', 'Hindi movies'],
    },
    'Telugu': {
        'code': 'te', 'youtube_code': 'te',
        'subscribe_cta': 'సబ్స్క్రైబ్ చేయండి',
        'watch_cta': 'ఈ వీడియో చూడండి',
        'keywords_extra': ['Telugu serial', 'Tollywood', 'Zee Telugu', 'Gemini TV',
                           'Star Maa', 'Telugu drama', 'Telugu movies', 'Andhra'],
    },
    'Urdu': {
        'code': 'ur', 'youtube_code': 'ur',
        'subscribe_cta': 'سبسکرائب کریں',
        'watch_cta': 'یہ ویڈیو دیکھیں',
        'keywords_extra': ['Urdu drama', 'Pakistani TV', 'Zee Zindagi', 'ARY Digital',
                           'Urdu serial', 'Desi drama', 'South Asian entertainment'],
    },
    'Malayalam': {
        'code': 'ml', 'youtube_code': 'ml',
        'subscribe_cta': 'സബ്സ്ക്രൈബ് ചെയ്യൂ',
        'watch_cta': 'ഈ വീഡിയോ കാണൂ',
        'keywords_extra': ['Malayalam serial', 'Mollywood', 'Asianet', 'Mazhavil Manorama',
                           'Surya TV', 'Kerala entertainment', 'Malayalam movies'],
    },
    'Odia': {
        'code': 'or', 'youtube_code': 'or',
        'subscribe_cta': 'ସବ୍ସ୍କ୍ରାଇବ୍ କରନ୍ତୁ',
        'watch_cta': 'ଏହି ଭିଡ଼ିଓ ଦେଖନ୍ତୁ',
        'keywords_extra': ['Odia serial', 'Ollywood', 'Zee Sarthak', 'Tarang TV',
                           'Odia drama', 'Odisha entertainment', 'Odia movies'],
    },
    'Kannada': {
        'code': 'kn', 'youtube_code': 'kn',
        'subscribe_cta': 'ಸಬ್‌ಸ್ಕ್ರೈಬ್ ಮಾಡಿ',
        'watch_cta': 'ಈ ವೀಡಿಯೊ ನೋಡಿ',
        'keywords_extra': ['Kannada serial', 'Sandalwood', 'Zee Kannada', 'Star Suvarna',
                           'Udaya TV', 'Karnataka entertainment', 'Kannada movies'],
    },
    'Bengali': {
        'code': 'bn', 'youtube_code': 'bn',
        'subscribe_cta': 'সাবস্ক্রাইব করুন',
        'watch_cta': 'এই ভিডিওটি দেখুন',
        'keywords_extra': ['Bengali serial', 'Tollywood Bengali', 'Zee Bangla', 'Star Jalsha',
                           'Bengal entertainment', 'Bengali movies', 'Kolkata TV'],
    },
    'Marathi': {
        'code': 'mr', 'youtube_code': 'mr',
        'subscribe_cta': 'सबस्क्राइब करा',
        'watch_cta': 'हा व्हिडिओ पहा',
        'keywords_extra': ['Marathi serial', 'Zee Marathi', 'Star Pravah', 'Colors Marathi',
                           'Marathi drama', 'Maharashtra entertainment', 'Marathi movies'],
    },
    'English': {
        'code': 'en', 'youtube_code': 'en',
        'subscribe_cta': 'Subscribe',
        'watch_cta': 'Watch this video',
        'keywords_extra': ['Indian entertainment', 'Indian TV', 'Bollywood English',
                           'South Asian content', 'Desi entertainment', 'Indian drama'],
    },
}


def generate_metadata(clip, source_video):
    """
    Generate AI metadata for a clip.
    Tries Gemini API first, falls back to template-based generation.
    """
    language = source_video.language or 'Hindi'
    lang_cfg = LANG_CONFIG.get(language, LANG_CONFIG['Hindi'])

    try:
        return _gemini_metadata(clip, source_video, lang_cfg)
    except Exception as e:
        logger.warning(f'Gemini metadata failed: {e}. Using template fallback.')
        return _template_metadata(clip, source_video, lang_cfg)


def _gemini_metadata(clip, source_video, lang_cfg):
    """Generate metadata using Gemini 1.5 Flash."""
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')

    clip_type_label = {
        'shorts':   'YouTube Short (15-60 seconds vertical video)',
        'medium':   'Medium-length YouTube video (3-5 minutes)',
        'longform': 'Long-form YouTube video (10-30 minutes)',
        'full':     'Full-length episode/movie upload',
    }.get(clip.clip_type, 'YouTube video clip')

    prompt = f"""You are a YouTube SEO expert specializing in Indian entertainment content for {source_video.language} audiences.

Generate highly optimized YouTube metadata for a {clip_type_label} from {source_video.network} network.

Content Details:
- Source Title: {source_video.title}
- Network: {source_video.network}
- Language: {source_video.language}
- Genre: {source_video.genre}
- Content Type: {source_video.content_type}
- Clip Duration: {clip.duration:.0f} seconds
- Clip Position: {clip.start_time:.0f}s to {clip.end_time:.0f}s in source

Requirements:
1. Title: 55-65 characters, include show name + scene type + language keyword
2. Description: 250-400 words. Start with a strong hook (first 2 lines visible before "Show more"). Include scene description, network info, CTA to subscribe. Natural keyword placement. End with hashtags.
3. Tags: 28-30 highly relevant tags. Mix of: show name, network, language, genre, emotion keywords, Indian entertainment terms
4. Keywords: 10 high-value search terms people actually search for

IMPORTANT: Generate ALL text in English (for YouTube search optimization), but include the {source_video.language} show name and key terms naturally.

Respond ONLY with valid JSON, no markdown, no explanation:
{{
  "title": "string (55-65 chars)",
  "description": "string (250-400 words with hashtags at end)",
  "tags": ["tag1", "tag2", ... 28-30 tags],
  "keywords": ["kw1", "kw2", ... 10 keywords]
}}"""

    response = model.generate_content(prompt)
    text = response.text.strip()

    # Strip markdown code blocks if present
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if not json_match:
        raise ValueError('No JSON in Gemini response')

    data = json.loads(json_match.group())

    # Validate and cap
    title = str(data.get('title', '')).strip()[:100]
    if not title:
        title = _fallback_title(clip, source_video)

    description = str(data.get('description', '')).strip()
    tags = [str(t).strip() for t in data.get('tags', []) if t][:30]
    keywords = [str(k).strip() for k in data.get('keywords', []) if k][:10]

    # Add language-specific extra keywords
    tags = list(dict.fromkeys(tags + lang_cfg['keywords_extra']))[:30]
    keywords = list(dict.fromkeys(keywords + lang_cfg['keywords_extra'][:3]))[:10]

    # For Shorts, append #Shorts tag
    if clip.clip_type == 'shorts':
        if '#Shorts' not in tags:
            tags = ['#Shorts'] + tags
        if '#shorts' not in description.lower():
            description += '\n\n#Shorts #ShortVideo #Reels'

    return {
        'title':       title,
        'description': description,
        'tags':        tags[:30],
        'keywords':    keywords[:10],
    }


def _template_metadata(clip, source_video, lang_cfg):
    """Reliable fallback template metadata for all 10 languages."""
    title       = _fallback_title(clip, source_video)
    description = _fallback_description(clip, source_video, lang_cfg)
    tags        = _fallback_tags(source_video, lang_cfg)
    keywords    = lang_cfg['keywords_extra'][:5] + [
        source_video.title,
        f"{source_video.language} {source_video.genre}",
        f"{source_video.network} TV",
        "Indian entertainment",
        "Subscribe",
    ]

    return {
        'title':       title[:100],
        'description': description,
        'tags':        tags[:30],
        'keywords':    list(dict.fromkeys(keywords))[:10],
    }


def _fallback_title(clip, sv):
    type_labels = {
        'shorts':   'Best Moments',
        'medium':   'Full Scene',
        'longform': 'Full Episode',
        'full':     'Complete Video',
    }
    scene = type_labels.get(clip.clip_type, 'Highlights')
    t = f"{sv.title} - {scene} | {sv.language} {sv.genre} | {sv.network}"
    return t[:100]


def _fallback_description(clip, sv, lang_cfg):
    cta = lang_cfg.get('subscribe_cta', 'Subscribe')
    network_map = {
        'ZEE': 'Zee Entertainment', 'SUN': 'Sun Network',
        'ZEE_CINEMA': 'Zee Cinema', 'SUN_MUSIC': 'Sun Music',
    }
    network_full = network_map.get(sv.network, sv.network)

    dur_str = f"{int(clip.duration // 60)}m {int(clip.duration % 60)}s" if clip.duration >= 60 else f"{int(clip.duration)}s"

    return f"""Watch this exclusive {clip.clip_type} clip from {sv.title} — one of the most popular {sv.language} {sv.genre} shows on {network_full}!

🎬 About This Clip:
{sv.title} delivers powerful storytelling in {sv.language}. This {dur_str} clip features some of the most memorable moments from the show. Whether you love dramatic twists, emotional scenes, or action-packed sequences — this has it all!

📺 About {sv.title}:
{sv.title} is a premium {sv.genre} production from {network_full}, available in {sv.language}. Known for its compelling storylines, outstanding performances, and high production values, it has won millions of hearts across India and worldwide.

🌟 Why Watch This:
✔ Gripping {sv.genre} content
✔ {sv.language} entertainment at its best  
✔ From the trusted {sv.network} network
✔ Perfect for fans of Indian television

🔔 Don't miss new clips! {cta}:
• Like this video if you enjoyed it
• Share with friends and family  
• Turn on notifications for updates
• Comment your favorite scenes below!

#{sv.network}TV #{sv.language}Drama #{sv.genre} #IndianTV #Entertainment #{''.join(sv.title.split()[:2])} #{sv.language}Entertainment #IndianEntertainment #Zee #Sun
"""


def _fallback_tags(sv, lang_cfg):
    base_tags = [
        sv.title,
        sv.network,
        sv.language,
        sv.genre,
        f"{sv.language} Drama",
        f"{sv.language} Serial",
        f"{sv.network} TV",
        f"{sv.language} Entertainment",
        "Indian TV",
        "Indian Entertainment",
        "Best Scenes",
        "Emotional Scene",
        f"{sv.genre} Scene",
        "Indian Television",
        "TV Serial",
        f"{sv.language} Movies",
        "Latest Episodes",
        "Drama Serial",
        "Desi Entertainment",
        "South Asian TV",
    ]
    all_tags = base_tags + lang_cfg.get('keywords_extra', [])
    return list(dict.fromkeys(all_tags))[:30]
