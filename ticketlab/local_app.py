"""TicketLab web app that extracts records through an SGLang server.

Start SGLang first (see README.md). Requests use SGLang's JSON Schema
constrained decoding, the same mode as the reported benchmark. Ticket text is
sent only to the SGLang server given by --sglang-url (localhost by default).
"""
import argparse
import json
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ticketlab.schema import SCHEMA, messages, parse_output

ROOT = Path(__file__).resolve().parents[1]
MODEL_KIND = "selected"
SGLANG_URL = "http://127.0.0.1:30000"
LOCK = threading.Lock()


def sglang_ready():
    try:
        urllib.request.urlopen(SGLANG_URL + "/model_info", timeout=2).close()
        return True
    except Exception:
        return False


def extract(text):
    if not sglang_ready():
        raise ConnectionError("SGLang server is not reachable at " + SGLANG_URL + ". Start it as described in README.md.")
    body = {"model": "default", "messages": messages(text), "temperature": 0, "max_tokens": 256,
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "ticket", "schema": SCHEMA, "strict": True}}}
    request = urllib.request.Request(SGLANG_URL + "/v1/chat/completions", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=180) as response:
        output = json.load(response)["choices"][0]["message"]["content"]
    result = {"output": output, "latency_seconds": time.monotonic() - started,
              "checkpoint": checkpoint_name(),
              "decoding": "json_schema_constrained", "engine": "SGLang"}
    try:
        result.update(parsed=parse_output(output), schema_valid=True)
    except Exception as exc:
        result.update(parsed=None, schema_valid=False, error=str(exc))
    return result


def checkpoint_name():
    if MODEL_KIND == "base":
        return "Qwen/Qwen2.5-3B-Instruct"
    return json.loads((ROOT / "config/MODEL_SELECTION.json").read_text())["selected_checkpoint"]


def serve(port):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/api/status":
                return self.send_json(200, {"checkpoint": checkpoint_name(),
                                            "model": "Qwen2.5 · 3B", "engine": "SGLang",
                                            "ready": sglang_ready()})
            if self.path == "/api/results":
                path = ROOT / "metrics/comparison.json"
                return self.send_json(200, json.loads(path.read_text()) if path.exists() else [])
            paths = {"/": "index.html", "/style.css": "style.css", "/app.js": "app.js",
                     "/logo.png": "logo.png"}
            if self.path not in paths:
                return self.send_json(404, {"error": "Not found"})
            kind = ("text/html" if self.path == "/" else "text/css" if self.path.endswith("css")
                    else "image/png" if self.path.endswith("png") else "text/javascript")
            data = (ROOT / "web" / paths[self.path]).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.path != "/api/extract":
                return self.send_json(404, {"error": "Not found"})
            if self.headers.get("Origin") not in (None, f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
                return self.send_json(403, {"error": "Origin not allowed"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.send_json(400, {"error": "Invalid request length"})
            if size < 1 or size > 32000:
                return self.send_json(413, {"error": "Request size must be 1–32,000 bytes"})
            if not LOCK.acquire(blocking=False):
                return self.send_json(429, {"error": "An extraction is already running"})
            try:
                body = json.loads(self.rfile.read(size))
                text = body.get("text")
                if not isinstance(text, str) or not 1 <= len(text.strip()) <= 6000:
                    return self.send_json(400, {"error": "Enter a ticket between 1 and 6000 characters"})
                return self.send_json(200, extract(text))
            except Exception as exc:
                return self.send_json(502, {"error": str(exc)[:500]})
            finally:
                LOCK.release()

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"TicketLab local: http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--model", choices=["selected", "base"], default="selected",
                        help="label of the model served by SGLang")
    parser.add_argument("--sglang-url", default=SGLANG_URL)
    args = parser.parse_args()
    MODEL_KIND = args.model
    SGLANG_URL = args.sglang_url.rstrip("/")
    serve(args.port)
