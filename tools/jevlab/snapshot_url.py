#!/usr/bin/env python3
"""Render a URL to PNG via GTK4 + WebKit (for frames when scrot is blank)."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time


def _auth() -> None:
    os.environ.setdefault("DISPLAY", ":0")
    os.environ.setdefault("GDK_BACKEND", "x11")
    try:
        args = subprocess.check_output(
            ["ps", "-ww", "-C", "Xwayland", "-o", "args="], text=True
        )
    except Exception:
        return
    match = re.search(r"-auth ([^ ]+)", args)
    if match:
        os.environ["XAUTHORITY"] = match.group(1)


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: snapshot_url.py URL OUT.png", file=sys.stderr)
        return 2
    url, out = sys.argv[1], sys.argv[2]
    _auth()

    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("WebKit", "6.0")
    from gi.repository import GLib, Gtk, WebKit

    def on_load(view, event) -> None:
        if event != WebKit.LoadEvent.FINISHED:
            return

        def snap() -> bool:
            view.get_snapshot(
                WebKit.SnapshotRegion.FULL_DOCUMENT,
                WebKit.SnapshotOptions.NONE,
                None,
                on_snap,
                None,
            )
            return False

        GLib.timeout_add(1500, snap)

    def on_snap(view, result, _data) -> None:
        try:
            tex = view.get_snapshot_finish(result)
            tex.save_to_png(out)
            print("saved", out)
        except Exception as exc:  # noqa: BLE001
            print("snap fail", exc, file=sys.stderr)
            app.quit()
            return
        app.quit()

    # Probe the URL first — refuse blank "connection refused" PNGs.
    import urllib.error
    import urllib.request

    for _ in range(20):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    break
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.25)
    else:
        print(f"url not reachable: {url}", file=sys.stderr)
        return 3

    app = Gtk.Application(application_id=f"org.flycast.jevlab.snapshot.p{os.getpid()}")

    def activate(application: Gtk.Application) -> None:
        win = Gtk.ApplicationWindow(application=application, title="snapshot")
        view = WebKit.WebView()
        view.connect("load-changed", on_load)
        win.set_default_size(1600, 900)
        win.set_child(view)
        win.present()
        view.load_uri(url)

    app.connect("activate", activate)
    return app.run(None)


if __name__ == "__main__":
    raise SystemExit(main())
