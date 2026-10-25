# TicketLab

**Syntax Error 2026 · Local LLM · Structured extraction**

[Watch the local extraction demo](https://github.com/aditya-411/ticketlab/releases/download/models-v1/ticketlab-demo-h264.mp4).

TicketLab turns a customer support message into a seven-field JSON record:
`order_id`, `product`, `issue_type`, `quantity`, `requested_resolution`,
`prior_contacts`, and `needs_review`. Missing facts stay `null`; conflicting
or uncertain tickets are marked for review. The web app calls an SGLang server that you run yourself, so ticket text goes
only to that server.

## What we built

The base model is the pinned
[`Qwen/Qwen2.5-3B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct)
checkpoint at revision `aa8e72537993ba99e69dfaafa59ed015b17504d1`.
The current tuned model is a merged LoRA checkpoint, `ticket-3b-v7`, trained
for this extraction schema. The `models/selected` link points to the tuned
model used by the local app.

We generated synthetic support tickets, cleaned and deduplicated training
examples with Lexsi CuratorKIT, and fine-tuned the base model with Lexsi
AlignTune. We evaluated base and tuned checkpoints through SGLang JSON Schema
constrained decoding and Lexsi AuditKIT. The local app uses SGLang with the same JSON Schema
constrained decoding, serving the tuned model.

## Base versus tuned

Both models were scored on the same 263 synthetic development tickets with
SGLang constrained decoding. “Exact” means all seven fields match the target.

| Model | Exact records | Correct fields | Schema valid |
| --- | ---: | ---: | ---: |
| Base Qwen2.5-3B | 28.9% | 83.5% | 100% |
| Tuned `ticket-3b-v7` | 86.7% | 97.5% | 100% |

These synthetic scores do not establish accuracy on real customer tickets.
The values served in the web interface are in `metrics/comparison.json`.

## Repository guide

| Folder | Contents |
| --- | --- |
| `models/` | Base and tuned model metadata and the selected model link |
| `ticketlab/` | Local server and seven-field output schema |
| `web/` | Browser interface |
| `config/` | Local dependencies, checkpoint selection, and weight checksums |
| `scripts/` | Weight downloader for a fresh clone |
| `metrics/` | Base and tuned comparison shown by the interface |

## Run with SGLang

SGLang is the only inference engine this project uses. Any machine that
SGLang supports can serve the model; see the
[SGLang installation guide](https://docs.sglang.ai/get_started/install.html)
for your hardware. The tuned weights are merged 16-bit Qwen2.5-3B (about
6.2 GB), stored as GitHub Release parts and restored by the downloader.

```sh
git clone https://github.com/aditya-411/ticketlab.git
cd ticketlab
python3 -m venv .venv
.venv/bin/python -m pip install -r config/requirements-local.txt
.venv/bin/python -m pip install "sglang[all]"
.venv/bin/python scripts/download_weights.py
```

Terminal 1, the model server:

```sh
.venv/bin/python -m sglang.launch_server \
  --model-path models/ticket-3b-v7 --host 127.0.0.1 --port 30000
```

Terminal 2, the web app (open [http://127.0.0.1:8080](http://127.0.0.1:8080)):

```sh
.venv/bin/python -m ticketlab.local_app
```

Use `--sglang-url` to point the app at an SGLang server on another host. To
compare with the base model, run `scripts/download_weights.py --model base`,
serve `models/base` from SGLang on another port, and start the app with
`--model base --sglang-url http://127.0.0.1:30001 --port 8081`.

The app sends each ticket with the JSON Schema in `ticketlab/schema.py` as
the response format, which is the constrained decoding mode used in the
benchmark.

## Limits

The scores above used synthetic tickets and do not establish accuracy on real
customer tickets. Every output is validated against the schema, and human
review remains necessary for support decisions.
