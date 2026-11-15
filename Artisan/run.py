"""Start Artisan with ONE command (from the Artisan folder):

    python run.py

It starts the web server and opens the app in your browser.
Stop it with Ctrl+C.
"""
import threading
import webbrowser

import uvicorn

HOST, PORT = "127.0.0.1", 8000
URL = f"http://{HOST}:{PORT}"

if __name__ == "__main__":
    print(f"\n  Artisan Geo is starting -> {URL}\n  (first launch downloads NASA data: ~1 minute)\n")
    threading.Timer(2.0, lambda: webbrowser.open(URL)).start()
    uvicorn.run("backend.main:app", host=HOST, port=PORT)
