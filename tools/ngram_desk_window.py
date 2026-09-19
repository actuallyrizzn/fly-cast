#!/usr/bin/env python3
"""Status window on the ngram desktop. Reads ~/fly-cast-runs/desk_status.txt.

Snap Firefox cannot open the laptop display from an SSH-started job.
This window is the glass. Five lines in the status file:

1 job name
2 step
3 progress
4 elapsed
5 last numbers
"""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

STATUS = Path.home() / "fly-cast-runs" / "desk_status.txt"


class DeskWindow(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title="ngram — waiting")
        self.set_default_size(900, 700)
        self.set_keep_above(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_margin_top(36)
        box.set_margin_bottom(36)
        box.set_margin_start(36)
        box.set_margin_end(36)
        self.job = self._label("waiting", 32)
        self.step = self._label("", 22)
        self.progress = self._label("", 20)
        self.elapsed = self._label("", 20)
        self.numbers = self._label("", 20)
        for widget in (self.job, self.step, self.progress, self.elapsed, self.numbers):
            box.pack_start(widget, False, False, 0)
        self.add(box)
        self._style()
        GLib.timeout_add(2000, self._tick)
        self._tick()

    def _label(self, text: str, size: int) -> Gtk.Label:
        del size
        label = Gtk.Label(label=text, xalign=0)
        label.set_line_wrap(True)
        label.set_max_width_chars(40)
        return label

    def _style(self) -> None:
        css = b"""
        window { background: #1c1915; }
        label { color: #f4f0e6; font-family: sans-serif; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _tick(self) -> bool:
        lines = ["waiting", "", "", "", ""]
        if STATUS.exists():
            got = STATUS.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(got[:5]):
                lines[i] = line
        job = lines[0].strip() or "waiting"
        self.set_title(f"ngram — {job}")
        self.job.set_markup(f'<span size="32000" weight="bold">{_esc(job)}</span>')
        self.step.set_markup(f'<span size="22000">{_esc(lines[1])}</span>')
        self.progress.set_markup(f'<span size="20000">{_esc(lines[2])}</span>')
        self.elapsed.set_markup(f'<span size="20000">{_esc(lines[3])}</span>')
        self.numbers.set_markup(f'<span size="20000">{_esc(lines[4])}</span>')
        return True


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def main() -> int:
    win = DeskWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
