# downloader.py
# -------------
# Wraps the yt-dlp library (installed via pip) to:
#   1. Fetch info about a URL (title, thumbnail, duration, formats)
#   2. Download the chosen quality in a background thread
#   3. Support pause / resume / cancel while downloading
#
# IMPORTANT HONESTY NOTE:
# Pydroid 3 does not have ffmpeg available, which is normally used to
# merge separate high-quality video-only + audio-only streams into one
# file. Without it, this app can only save formats that already
# contain both video and audio together ("progressive" formats), which
# on YouTube usually tops out around 720p. This is a real platform
# limitation, not a bug -- see build_format_list() below.

import os
import time
import threading

try:
    import yt_dlp
except ImportError:
    # yt-dlp isn't installed yet. The app will show a clear message
    # instead of crashing -- see main.py's error handling.
    yt_dlp = None


class DownloadCancelled(Exception):
    # Raised inside the progress hook to make yt-dlp stop early.
    pass


class MediaDownloader:
    # One instance is created per download attempt so pause/cancel
    # flags never leak between unrelated downloads.

    def __init__(self):
        self._paused = False
        self._cancelled = False

    # ------------------------------------------------------------
    # STEP 1: look up info about the URL without downloading yet.
    # ------------------------------------------------------------
    def extract_info(self, url):
        if yt_dlp is None:
            raise RuntimeError("yt-dlp is not installed. Install it with: pip install yt-dlp")

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return info

    # ------------------------------------------------------------
    # Turns yt-dlp's raw format list into a short, friendly list of
    # choices the UI can show in a dropdown.
    # ------------------------------------------------------------
    def build_format_list(self, info):
        formats = info.get("formats") or []
        progressive = []  # formats that already have video + audio together
        seen_heights = set()

        for f in formats:
            has_video = f.get("vcodec") not in (None, "none")
            has_audio = f.get("acodec") not in (None, "none")
            height = f.get("height")
            if has_video and has_audio and height:
                if height in seen_heights:
                    continue
                seen_heights.add(height)
                progressive.append({
                    "label": "{}p".format(height),
                    "selector": f.get("format_id"),
                    "filesize": f.get("filesize") or f.get("filesize_approx"),
                })

        progressive.sort(key=lambda x: int(x["label"].replace("p", "")), reverse=True)

        options = [{"label": "Best available (auto)", "selector": "best", "filesize": None}]
        options += progressive
        options.append({"label": "Audio Only", "selector": "bestaudio/best", "filesize": None})
        return options

    # ------------------------------------------------------------
    # STEP 2: actually download, in a background thread so the UI
    # doesn't freeze. progress_cb/done_cb/error_cb are all called
    # from the background thread -- the caller (main.py) is
    # responsible for hopping back to the main thread (Clock) before
    # touching any Kivy widgets.
    # ------------------------------------------------------------
    def download(self, url, selector, dest_folder, progress_cb, done_cb, error_cb):
        thread = threading.Thread(
            target=self._run_download,
            args=(url, selector, dest_folder, progress_cb, done_cb, error_cb),
            daemon=True,
        )
        thread.start()
        return thread

    def _run_download(self, url, selector, dest_folder, progress_cb, done_cb, error_cb):
        if yt_dlp is None:
            error_cb("yt-dlp is not installed. Install it with: pip install yt-dlp")
            return

        outtmpl = os.path.join(dest_folder, "%(title)s.%(ext)s")
        ydl_opts = {
            "format": selector,
            "outtmpl": outtmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self._make_hook(progress_cb)],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)
            done_cb(filepath)
        except DownloadCancelled:
            error_cb("Download cancelled.")
        except Exception as e:
            error_cb(str(e))

    def _make_hook(self, progress_cb):
        # Returns a function yt-dlp calls repeatedly while downloading.
        def hook(d):
            # PAUSE: block this same thread before it reads the next
            # chunk. yt-dlp won't progress until this function returns,
            # so looping here genuinely pauses the transfer.
            while self._paused and not self._cancelled:
                time.sleep(0.3)

            if self._cancelled:
                raise DownloadCancelled()

            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)
                percent = (downloaded / total * 100) if total else None
                progress_cb(percent, downloaded, total, d.get("speed"), d.get("eta"))
            elif d.get("status") == "finished":
                progress_cb(100, d.get("downloaded_bytes"), d.get("total_bytes"), 0, 0)

        return hook

    # ------------------------------------------------------------
    # Controls -- called from the UI thread, just flip flags that
    # the background thread's hook function checks.
    # ------------------------------------------------------------
    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def cancel(self):
        self._cancelled = True
        self._paused = False
