"""Local-only admin panel. Does not run on Bothost (entry is repo-root main.py)."""
from __future__ import annotations

import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DIR = Path(__file__).resolve().parent
HOST = os.environ.get("GUI_HOST", "127.0.0.1")
PORT = int(os.environ.get("GUI_PORT", "43122"))
DEFAULT_BOT_API = "https://bot-1787963517-5953-petrel.bothost.tech"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(DIR), **kwargs)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"gui {self.address_string()} {fmt % args}", flush=True)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in {"/", "/gui", "/admin", "/admin.html"}:
            html = (DIR / "admin.html").read_text(encoding="utf-8")
            html = html.replace(
                "__BOT_API_URL__",
                (os.environ.get("BOT_API_URL") or DEFAULT_BOT_API).strip(),
            )
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()


def main() -> None:
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Local GUI http://{HOST}:{PORT}/  (bot stays on the server)", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
