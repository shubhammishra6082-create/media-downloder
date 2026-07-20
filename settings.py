# settings.py
# -----------
# Small persisted app settings (download folder, dark/light mode),
# stored as plain JSON, plus the Settings screen's behavior.
# The KV file (media_downloader.kv) defines this screen's layout;
# this file defines what happens when you tap its buttons.

import json
import os

from kivymd.uix.screen import MDScreen
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.dialog import MDDialog

import utils
import database

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


class SettingsManager:
    # Loads/saves the small settings.json file.

    def __init__(self):
        self.data = {
            "download_folder": None,  # None = use the auto-detected default
            "dark_mode": True,
        }
        self.load()

    def load(self):
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, "r") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
            except (ValueError, OSError):
                pass

    def save(self):
        with open(SETTINGS_PATH, "w") as f:
            json.dump(self.data, f, indent=2)

    def get_download_folder(self):
        # Falls back to the auto-detected default if nothing set yet.
        if self.data.get("download_folder"):
            return self.data["download_folder"]
        folder, _ = utils.ensure_download_folder()
        return folder

    def set_download_folder(self, path):
        self.data["download_folder"] = path
        self.save()

    def is_dark_mode(self):
        return self.data.get("dark_mode", True)

    def set_dark_mode(self, value):
        self.data["dark_mode"] = value
        self.save()


class SettingsScreen(MDScreen):
    # Behavior for the Settings screen. The App instance sets
    # self.app and self.settings_manager right after creating this
    # screen (see main.py).

    def on_pre_enter(self):
        self.refresh_folder_label()

    def refresh_folder_label(self):
        folder = self.app.settings_manager.get_download_folder()
        self.ids.current_folder_label.text = "Current folder:\n{}".format(folder)

    def save_folder(self):
        new_path = self.ids.folder_input.text.strip()
        if not new_path:
            return
        confirmed_path, error = utils.ensure_download_folder(new_path)
        if error:
            self.show_dialog("Cannot use that folder", error)
            return
        self.app.settings_manager.set_download_folder(confirmed_path)
        self.ids.folder_input.text = ""
        self.refresh_folder_label()
        self.show_dialog("Saved", "Downloads will now be saved to:\n{}".format(confirmed_path))

    def toggle_theme(self):
        is_dark = self.app.settings_manager.is_dark_mode()
        new_value = not is_dark
        self.app.settings_manager.set_dark_mode(new_value)
        self.app.theme_cls.theme_style = "Dark" if new_value else "Light"
        self.ids.theme_button.text = "Switch to Light Mode" if new_value else "Switch to Dark Mode"

    def confirm_clear_history(self):
        self.dialog = MDDialog(
            title="Clear all history?",
            text="This will permanently delete your download history list (downloaded files themselves are NOT deleted).",
            buttons=[
                MDRaisedButton(text="CANCEL", on_release=lambda i: self.dialog.dismiss()),
                MDRaisedButton(
                    text="CLEAR",
                    md_bg_color=(0.9, 0.2, 0.2, 1),
                    on_release=lambda i: self.do_clear_history(),
                ),
            ],
        )
        self.dialog.open()

    def do_clear_history(self):
        self.app.db.clear_all()
        self.dialog.dismiss()
        self.show_dialog("Done", "History cleared.")

    def show_dialog(self, title, text):
        d = MDDialog(title=title, text=text, buttons=[MDRaisedButton(text="OK", on_release=lambda i: d.dismiss())])
        d.open()
