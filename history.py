# history.py
# ----------
# Behavior for the History screen: lists past downloads from the
# database, supports searching them, and lets you delete entries.
# Layout lives in media_downloader.kv; this file wires up the buttons.

from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.screen import MDScreen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDIconButton


class HistoryScreen(MDScreen):
    # self.app is set by main.py right after this screen is created.

    def on_pre_enter(self):
        self.refresh(self.app.db.get_all())

    def do_search(self):
        keyword = self.ids.search_input.text.strip()
        if keyword:
            self.refresh(self.app.db.search(keyword))
        else:
            self.refresh(self.app.db.get_all())

    def refresh(self, entries):
        box = self.ids.history_list_box
        box.clear_widgets()
        if not entries:
            box.add_widget(MDLabel(
                text="No downloads yet.",
                halign="center",
                theme_text_color="Custom",
                text_color=(0.6, 0.6, 0.65, 1),
                size_hint_y=None,
                height="40dp",
            ))
            return
        for entry in entries:
            box.add_widget(self.build_entry_card(entry))

    def build_entry_card(self, entry):
        status_colors = {
            "Completed": (0.3, 0.9, 0.4, 1),
            "Failed": (0.9, 0.3, 0.3, 1),
            "Cancelled": (0.9, 0.7, 0.2, 1),
            "Downloading": (0.3, 0.7, 1, 1),
        }
        color = status_colors.get(entry["status"], (0.7, 0.7, 0.75, 1))

        card = MDCard(
            orientation="vertical",
            size_hint_y=None,
            height="100dp",
            padding="10dp",
            spacing="4dp",
            md_bg_color=(0.08, 0.09, 0.13, 1),
            radius=[12, 12, 12, 12],
        )

        top = BoxLayout(size_hint_y=None, height="26dp")
        top.add_widget(MDLabel(
            text=entry["title"] or "Untitled",
            bold=True,
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1),
        ))
        top.add_widget(MDLabel(
            text=entry["status"],
            size_hint_x=0.35,
            theme_text_color="Custom",
            text_color=color,
        ))
        card.add_widget(top)

        card.add_widget(MDLabel(
            text="{} | {}".format(entry["platform"], entry["date_added"][:16]),
            theme_text_color="Custom",
            text_color=(0.7, 0.7, 0.75, 1),
            font_style="Caption",
            size_hint_y=None,
            height="20dp",
        ))

        bottom = BoxLayout(size_hint_y=None, height="30dp")
        bottom.add_widget(MDLabel(
            text=entry["filepath"] or "(not saved)",
            theme_text_color="Custom",
            text_color=(0.5, 0.5, 0.55, 1),
            font_style="Caption",
            shorten=True,
        ))
        bottom.add_widget(MDIconButton(
            icon="trash-can",
            theme_text_color="Custom",
            text_color=(0.9, 0.3, 0.3, 1),
            on_release=lambda i, eid=entry["id"]: self.delete_entry(eid),
        ))
        card.add_widget(bottom)
        return card

    def delete_entry(self, entry_id):
        self.app.db.delete_entry(entry_id)
        self.refresh(self.app.db.get_all())
