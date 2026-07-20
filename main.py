# main.py
# -------
# Entry point for the "Media Downloader" app.
# Run THIS file in Pydroid 3.
#
# This file defines the Home screen's behavior (URL analyze +
# download + progress UI) and wires up the whole App: loading the KV
# layout, connecting the bottom nav, and passing shared objects
# (database, settings) to the other screens.

import os
import threading

from kivy.lang import Builder
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.uix.boxlayout import BoxLayout

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDRaisedButton, MDIconButton
from kivymd.uix.label import MDLabel
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.dialog import MDDialog

import utils
from database import HistoryDatabase
from downloader import MediaDownloader
from settings import SettingsManager, SettingsScreen

# Storage permissions must be requested at RUNTIME on real Android
# (this wasn't needed inside Pydroid 3 itself, but is required once
# packaged as a standalone APK). The "android" module only exists
# when running on an actual Android device via python-for-android,
# so this is wrapped in try/except to still work fine on Pydroid 3
# or desktop testing.
try:
    from android.permissions import request_permissions, Permission
    ANDROID_PERMISSIONS_AVAILABLE = True
except ImportError:
    ANDROID_PERMISSIONS_AVAILABLE = False
from history import HistoryScreen

APP_DIR = os.path.dirname(os.path.abspath(__file__))
KV_PATH = os.path.join(APP_DIR, "media_downloader.kv")


class HomeScreen(MDScreen):
    # self.app is set by MediaDownloaderApp right after creating this
    # screen (see build()). current_info holds the last Analyze
    # result; current_downloader is the active MediaDownloader (or
    # None when nothing is downloading).

    current_info = None
    current_downloader = None
    current_history_id = None

    # ------------------------------------------------------------
    # URL BOX BUTTONS
    # ------------------------------------------------------------
    def paste_url(self):
        try:
            self.ids.url_input.text = Clipboard.paste()
        except Exception:
            pass

    def clear_url(self):
        self.ids.url_input.text = ""
        self.ids.platform_label.text = ""
        self.ids.info_box.clear_widgets()
        self.current_info = None

    # ------------------------------------------------------------
    # ANALYZE
    # ------------------------------------------------------------
    def analyze_url(self):
        url = self.ids.url_input.text.strip()
        if not utils.is_valid_url(url):
            self.show_dialog("Invalid URL", "That doesn't look like a valid web link. Make sure it starts with http:// or https://")
            return

        platform = utils.detect_platform(url)
        self.ids.platform_label.text = "Detected platform: {}".format(platform)
        self.ids.info_box.clear_widgets()
        self.ids.info_box.add_widget(MDLabel(text="Analyzing...", size_hint_y=None, height="30dp"))

        # Network calls must never run on the UI thread, or the whole
        # app freezes -- run extract_info() in a background thread.
        threading.Thread(target=self._analyze_thread, args=(url, platform), daemon=True).start()

    def _analyze_thread(self, url, platform):
        downloader = MediaDownloader()
        try:
            info = downloader.extract_info(url)
            options = downloader.build_format_list(info)
            Clock.schedule_once(lambda dt: self._show_info(url, platform, info, options))
        except Exception as e:
            Clock.schedule_once(lambda dt: self.show_dialog("Could not analyze this link", str(e)))
            Clock.schedule_once(lambda dt: self.ids.info_box.clear_widgets())

    def _show_info(self, url, platform, info, options):
        self.current_info = {"url": url, "platform": platform, "info": info, "options": options}
        box = self.ids.info_box
        box.clear_widgets()

        card = MDCard(
            orientation="vertical", padding="10dp", spacing="8dp",
            size_hint_y=None, height="330dp",
            md_bg_color=(0.08, 0.09, 0.13, 1), radius=[12, 12, 12, 12],
        )

        thumb_url = info.get("thumbnail")
        if thumb_url:
            from kivy.uix.image import AsyncImage
            card.add_widget(AsyncImage(source=thumb_url, size_hint_y=None, height="160dp"))

        card.add_widget(MDLabel(
            text=info.get("title") or "Untitled",
            bold=True, size_hint_y=None, height="24dp",
            theme_text_color="Custom", text_color=(1, 1, 1, 1),
        ))
        card.add_widget(MDLabel(
            text="Duration: {}".format(utils.format_duration(info.get("duration"))),
            size_hint_y=None, height="20dp",
            theme_text_color="Custom", text_color=(0.7, 0.7, 0.75, 1),
        ))

        from kivy.uix.spinner import Spinner
        quality_spinner = Spinner(
            text=options[0]["label"],
            values=[o["label"] for o in options],
            size_hint_y=None, height="40dp",
        )
        card.add_widget(quality_spinner)
        self._quality_spinner = quality_spinner
        self._format_options = options

        download_btn = MDRaisedButton(text="DOWNLOAD", md_bg_color=(0.2, 0.5, 0.9, 1), size_hint_y=None, height="40dp")
        download_btn.bind(on_release=lambda i: self.start_download())
        card.add_widget(download_btn)

        # Progress row (hidden until a download starts).
        self._progress_bar = MDProgressBar(value=0, max=100, size_hint_y=None, height="6dp")
        self._progress_label = MDLabel(text="", size_hint_y=None, height="20dp", theme_text_color="Custom", text_color=(0.7, 0.9, 1, 1))
        card.add_widget(self._progress_bar)
        card.add_widget(self._progress_label)

        controls = BoxLayout(size_hint_y=None, height="36dp", spacing="6dp")
        self._pause_btn = MDIconButton(icon="pause", on_release=lambda i: self.pause_download())
        self._resume_btn = MDIconButton(icon="play", on_release=lambda i: self.resume_download())
        self._cancel_btn = MDIconButton(icon="close-circle", theme_text_color="Custom", text_color=(0.9, 0.3, 0.3, 1), on_release=lambda i: self.cancel_download())
        controls.add_widget(self._pause_btn)
        controls.add_widget(self._resume_btn)
        controls.add_widget(self._cancel_btn)
        card.add_widget(controls)

        box.add_widget(card)

    # ------------------------------------------------------------
    # DOWNLOAD
    # ------------------------------------------------------------
    def start_download(self):
        if not self.current_info:
            return
        selected_label = self._quality_spinner.text
        selector = next((o["selector"] for o in self._format_options if o["label"] == selected_label), "best")

        folder = self.app.settings_manager.get_download_folder()
        confirmed_folder, error = utils.ensure_download_folder(folder)
        if error:
            self.show_dialog("Storage error", error)
            return

        title = self.current_info["info"].get("title") or "Untitled"
        url = self.current_info["url"]
        platform = self.current_info["platform"]

        self.current_history_id = self.app.db.add_entry(title, url, platform, "", "Downloading")
        self.current_downloader = MediaDownloader()
        self._progress_label.text = "Starting..."

        self.current_downloader.download(
            url, selector, confirmed_folder,
            progress_cb=self._on_progress,
            done_cb=self._on_done,
            error_cb=self._on_error,
        )

    def pause_download(self):
        if self.current_downloader:
            self.current_downloader.pause()

    def resume_download(self):
        if self.current_downloader:
            self.current_downloader.resume()

    def cancel_download(self):
        if self.current_downloader:
            self.current_downloader.cancel()
            if self.current_history_id:
                self.app.db.update_status(self.current_history_id, "Cancelled")

    # These three callbacks run on the BACKGROUND thread (they're
    # called from inside downloader.py) -- always hop back to the
    # main thread with Clock before touching any widget.
    def _on_progress(self, percent, downloaded, total, speed, eta):
        Clock.schedule_once(lambda dt: self._update_progress_ui(percent, downloaded, total))

    def _update_progress_ui(self, percent, downloaded, total):
        if percent is not None:
            self._progress_bar.value = percent
            self._progress_label.text = "{:.0f}% - {} / {}".format(
                percent, utils.format_filesize(downloaded), utils.format_filesize(total)
            )
        else:
            self._progress_label.text = "{} downloaded".format(utils.format_filesize(downloaded))

    def _on_done(self, filepath):
        Clock.schedule_once(lambda dt: self._finish_download(filepath))

    def _finish_download(self, filepath):
        self._progress_label.text = "Completed!"
        self._progress_bar.value = 100
        if self.current_history_id:
            self.app.db.update_status(self.current_history_id, "Completed", filepath)
        self.current_downloader = None

    def _on_error(self, message):
        Clock.schedule_once(lambda dt: self._show_error(message))

    def _show_error(self, message):
        self._progress_label.text = "Failed."
        if self.current_history_id:
            status = "Cancelled" if "cancel" in message.lower() else "Failed"
            self.app.db.update_status(self.current_history_id, status)
        self.current_downloader = None
        if "cancel" not in message.lower():
            self.show_dialog("Download failed", message)

    # ------------------------------------------------------------
    def show_dialog(self, title, text):
        d = MDDialog(title=title, text=text, buttons=[MDRaisedButton(text="OK", on_release=lambda i: d.dismiss())])
        d.open()


class MediaDownloaderApp(MDApp):
    def build(self):
        self.title = "Media Downloader"

        if ANDROID_PERMISSIONS_AVAILABLE:
            request_permissions([
                Permission.INTERNET,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
            ])

        self.settings_manager = SettingsManager()
        self.theme_cls.theme_style = "Dark" if self.settings_manager.is_dark_mode() else "Light"
        self.theme_cls.primary_palette = "Blue"

        self.db = HistoryDatabase()

        root = Builder.load_file(KV_PATH)

        # Give each screen a reference back to this App instance so
        # they can reach self.app.db / self.app.settings_manager.
        root.ids.home_screen.app = self
        root.ids.history_screen.app = self
        root.ids.settings_screen.app = self

        return root

    def switch_screen(self, name):
        self.root.ids.sm.current = name


if __name__ == "__main__":
    MediaDownloaderApp().run()
