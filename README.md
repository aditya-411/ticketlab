# TicketLab

**Syntax Error 2026 · Local LLM · Structured extraction**

[Watch the local extraction demo](https://github.com/aditya-411/ticketlab/releases/download/models-v1/ticketlab-demo-h264.mp4).

TicketLab turns a customer support message into a seven-field JSON record:
`order_id`, `product`, `issue_type`, `quantity`, `requested_resolution`,
`prior_contacts`, and `needs_review`. Missing facts stay `null`; conflicting
or uncertain tickets are marked for review. The web app serves locally and
sends ticket text only to the model on your Mac.

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
constrained decoding and Lexsi AuditKIT. The local app uses MLX-LM greedy
decoding, so its outputs can differ from the SGLang benchmark.

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
| `models/` | Base and tuned model metadata, selected model link, and 4-bit local runtime |
| `ticketlab/` | Local server and seven-field output schema |
| `web/` | Browser interface |
| `config/` | Local dependencies, checkpoint selection, and weight checksums |
| `scripts/` | Weight downloader for a fresh clone |
| `metrics/` | Base and tuned comparison shown by the interface |

Full precision base and tuned weights remain in the prepared local folder.
GitHub stores the 4-bit tuned weight as a Release asset; the pinned base can
be downloaded from Hugging Face. A fresh clone can run the tuned model with:

```sh
git clone https://github.com/aditya-411/ticketlab.git
cd ticketlab
python3 -m venv .venv
.venv/bin/python -m pip install -r config/requirements-local.txt
.venv/bin/python scripts/download_weights.py
.venv/bin/python -m ticketlab.local_app
```

## Run the tuned model locally

Use an Apple Silicon Mac. This workflow targets an M3 MacBook Air with 8 GB
RAM. The web interface and local HTTP endpoints have been smoke-tested, and a
1.6 GB 4-bit conversion artifact is present in the prepared folder. A local
inference run on the included sample ticket produced a schema-valid record
with the expected seven fields. Free memory before conversion,
since the merged source weights occupy about 6.17 GB.

In the prepared local folder, the 4-bit tuned weight already exists. Start
the server directly:

```sh
cd "/Users/adityajain/Desktop/syntax error 2026/submission"
python3 -m venv .venv
.venv/bin/python -m pip install -r config/requirements-local.txt
.venv/bin/python -m ticketlab.local_app
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080). Later runs need only
the last command. The server binds to
`127.0.0.1`, and inference does not call an online model.

To test the base model with the same interface, convert `models/base` to a
separate MLX folder. Do not overwrite the tuned conversion folder.

```sh
.venv/bin/python scripts/download_weights.py --model base
.venv/bin/python -m mlx_lm convert --hf-path models/base \
  --mlx-path models/base-mlx-4bit --quantize --q-bits 4
.venv/bin/python -m ticketlab.local_app --model base --port 8081
```

Open [http://127.0.0.1:8081](http://127.0.0.1:8081) for the base model.

## Limits

The scores above used synthetic tickets and SGLang constrained decoding. The
local MLX interface uses greedy decoding and validates each output against
the schema. Human review remains necessary for support decisions.
