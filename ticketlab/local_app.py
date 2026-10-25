"""Local-only TicketLab web app backed by an MLX model on Apple Silicon.

The model is loaded lazily on the first extraction request. No cloud request is
made by this program. Run the documented 4-bit conversion before starting it.
"""
import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ticketlab.schema import messages, parse_output

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models/selected-mlx-4bit"
MODEL_KIND = "selected"
LOCK = threading.Lock()
MODEL = None
TOKENIZER = None


def extract(text):
    global MODEL, TOKENIZER
    from mlx_lm import generate, load

    if not any(MODEL_PATH.glob("*.safetensors")):
        raise FileNotFoundError("The 4-bit local model is missing. Run the conversion command in README.md first.")
    if MODEL is None:
        MODEL, TOKENIZER = load(str(MODEL_PATH))
    prompt = TOKENIZER.apply_chat_template(messages(text), tokenize=False,
                                           add_generation_prompt=True)
    started = time.monotonic()
    output = generate(MODEL, TOKENIZER, prompt=prompt, max_tokens=256,
                      verbose=False)
    result = {"output": output, "latency_seconds": time.monotonic() - started,
              "checkpoint": checkpoint_name(),
              "decoding": "local_greedy", "engine": "MLX-LM"}
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
                                            "model": "Qwen2.5 · 3B", "engine": "MLX-LM",
                                            "ready": any(MODEL_PATH.glob("*.safetensors"))})
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
    parser.add_argument("--model", choices=["selected", "base"], default="selected")
    args = parser.parse_args()
    MODEL_KIND = args.model
    MODEL_PATH = ROOT / f"models/{args.model}-mlx-4bit"
    serve(args.port)
