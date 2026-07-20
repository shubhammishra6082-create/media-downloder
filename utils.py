# utils.py
# --------
# Small, dependency-free helper functions used across the app.
# Nothing in this file needs yt-dlp or Kivy, so it can be tested
# completely on its own.

import os
import re
from urllib.parse import urlparse

# Known platform domains -> friendly display name.
# Anything not in this list still works (yt-dlp supports 1800+ sites),
# it just shows up as "Other (auto-detected)".
KNOWN_PLATFORMS = {
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "m.youtube.com": "YouTube",
    "instagram.com": "Instagram",
    "www.instagram.com": "Instagram",
    "twitter.com": "Twitter / X",
    "x.com": "Twitter / X",
    "tiktok.com": "TikTok",
    "www.tiktok.com": "TikTok",
    "facebook.com": "Facebook",
    "fb.watch": "Facebook",
    "vimeo.com": "Vimeo",
    "soundcloud.com": "SoundCloud",
}


def is_valid_url(text):
    # Very basic sanity check: has http/https scheme and a domain.
    if not text:
        return False
    text = text.strip()
    try:
        result = urlparse(text)
        return result.scheme in ("http", "https") and bool(result.netloc)
    except Exception:
        return False


def detect_platform(url):
    # Returns a friendly platform name based on the URL's domain.
    try:
        domain = urlparse(url.strip()).netloc.lower()
        domain = domain.replace("www.", "") if domain.startswith("www.") else domain
        for key, name in KNOWN_PLATFORMS.items():
            if key.replace("www.", "") in domain:
                return name
        return "Other (auto-detected)"
    except Exception:
        return "Unknown"


def format_duration(seconds):
    # Converts seconds -> "MM:SS" or "H:MM:SS". Returns "Unknown" if missing.
    if seconds is None:
        return "Unknown"
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "Unknown"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return "{}:{:02d}:{:02d}".format(hours, minutes, secs)
    return "{}:{:02d}".format(minutes, secs)


def format_filesize(num_bytes):
    # Converts raw byte count -> human readable string, e.g. "12.4 MB".
    if not num_bytes:
        return "Unknown"
    try:
        num_bytes = float(num_bytes)
    except (TypeError, ValueError):
        return "Unknown"
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024.0:
            return "{:.1f} {}".format(num_bytes, unit)
        num_bytes /= 1024.0
    return "{:.1f} TB".format(num_bytes)


def sanitize_filename(name):
    # Removes characters that are not safe for file names on Android.
    if not name:
        return "media_file"
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    return cleaned.strip()[:120] or "media_file"


def default_download_dir():
    # The folder we try first: the shared Downloads folder, inside a
    # "Media Downloader" subfolder, matching common Android layout.
    candidates = [
        "/storage/emulated/0/Download/Media Downloader",
        os.path.join(os.path.expanduser("~"), "Downloads", "Media Downloader"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "Downloads", "Media Downloader"),
    ]
    return candidates


def ensure_download_folder(preferred_path=None):
    # Tries to create/use the preferred path; falls back to safer
    # alternatives if storage permission isn't available yet.
    # Returns (path, error_message_or_None).
    paths_to_try = [preferred_path] if preferred_path else []
    paths_to_try += default_download_dir()

    last_error = None
    for path in paths_to_try:
        if not path:
            continue
        try:
            os.makedirs(path, exist_ok=True)
            # Confirm we can actually write here.
            test_file = os.path.join(path, ".write_test")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            return path, None
        except Exception as e:
            last_error = str(e)
            continue
    return None, last_error or "Could not create a writable download folder."
