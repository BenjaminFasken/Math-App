"""
serve.py — Simple HTTP dev server for MathApp.
Run:  python serve.py
Then open http://localhost:8000
"""
import http.server
import socketserver
import mimetypes
import os

# Ensure .whl files (Python wheels) are served correctly
mimetypes.add_type('application/zip', '.whl')

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # CORS headers for local development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

if __name__ == '__main__':
    os.chdir(DIRECTORY)
    with ThreadedTCPServer(('', PORT), Handler) as httpd:
        print(f'MathApp dev server running at http://localhost:{PORT}')
        print('Press Ctrl+C to stop.')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nShutting down.')
