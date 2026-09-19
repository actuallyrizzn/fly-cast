#!/usr/bin/env python3
"""Open the watch URL in a GTK 4 + WebKit window on DISPLAY=:0."""

from __future__ import annotations

import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, WebKit  # noqa: E402


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
    title = sys.argv[2] if len(sys.argv) > 2 else "Fly probe"
    os.environ.setdefault("GDK_BACKEND", "x11")

    def on_activate(app: Gtk.Application) -> None:
        win = Gtk.ApplicationWindow(application=app, title=title)
        win.set_default_size(1600, 900)
        view = WebKit.WebView()
        view.load_uri(url)
        win.set_child(view)
        win.present()

    # Unique id so a second watch (smoke while grid is up) does not hand off
    # to the primary Gtk instance and exit, killing its http.server.
    app = Gtk.Application(application_id=f"org.flycast.jevlab.watch.{os.getpid()}")
    app.connect("activate", on_activate)
    return app.run(None)


if __name__ == "__main__":
    raise SystemExit(main())
