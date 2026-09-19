#!/usr/bin/env python3
"""Status window on the ngram desktop. Reads ~/fly-cast-runs/desk_status.txt.

Snap Firefox cannot open the laptop display from an SSH-started job.
This GTK window is the glass. Five lines in the status file:

1 job name
2 step
3 progress
4 elapsed
5 last numbers
"""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

STATUS = Path.home() / "fly-cast-runs" / "desk_status.txt"


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class DeskApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id="corp.decisionscience.ngramdesk")
        self.win: Gtk.ApplicationWindow | None = None
        self.labels: list[Gtk.Label] = []

    def do_activate(self) -> None:
        if self.win is not None:
            self.win.present()
            return
        win = Gtk.ApplicationWindow(application=self, title="ngram — waiting")
        win.set_default_size(900, 700)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(36)
        box.set_margin_bottom(36)
        box.set_margin_start(36)
        box.set_margin_end(36)
        sizes = (32000, 22000, 20000, 20000, 20000)
        for size in sizes:
            label = Gtk.Label(xalign=0)
            label.set_wrap(True)
            label.set_max_width_chars(42)
            label.set_markup(f'<span size="{size}"> </span>')
            box.append(label)
            self.labels.append(label)
        win.set_child(box)
        self._style()
        win.present()
        self.win = win
        GLib.timeout_add(2000, self._tick)
        self._tick()

    def _style(self) -> None:
        css = Gtk.CssProvider()
        css.load_from_data(
            b"window { background-color: #1c1915; } label { color: #f4f0e6; }"
        )
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def _tick(self) -> bool:
        lines = ["waiting", "", "", "", ""]
        if STATUS.exists():
            for i, line in enumerate(STATUS.read_text(encoding="utf-8").splitlines()[:5]):
                lines[i] = line
        job = lines[0].strip() or "waiting"
        if self.win is not None:
            self.win.set_title(f"ngram — {job}")
        sizes = (32000, 22000, 20000, 20000, 20000)
        weights = ("bold", "normal", "normal", "normal", "normal")
        for label, text, size, weight in zip(self.labels, lines, sizes, weights):
            label.set_markup(
                f'<span size="{size}" weight="{weight}">{_esc(text)}</span>'
            )
        return True


def main() -> int:
    app = DeskApp()
    return int(app.run(None) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
