"""
keep_alive.py
Starts a tiny web server so Render's free tier doesn't kill the bot.
Import this in telegram_broadcast_bot.py
"""

from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def log_message(self, format, *args):
        pass  # Silence request logs


def keep_alive():
    server = HTTPServer(("0.0.0.0", 8080), Handler)
    thread = Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    print("✅ Keep-alive server started on port 8080")
