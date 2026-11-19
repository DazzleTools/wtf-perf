"""probe_lmstudio_stream.py -- phase M measurement (b), licensed 2026-11-18.

Questions: with stream:true, does LM Studio deliver reasoning and content as
separate delta fields; what does the last chunk carry (finish_reason, usage
when stream_options.include_usage is set); and does closing the connection
mid-stream cancel the generation?

Prediction written before running: deltas carry `content`, and `reasoning_content`
(or `reasoning`) only when the model thinks; the last chunk has finish_reason
"stop" or "length" and, with include_usage, a usage object; closing mid-stream
logs "cancel task" (as the C# client measured, 0.4 s).

Method: two requests to the loaded model. (1) a short answer streamed to the
end, counting delta keys and reading the final chunk. (2) a long answer,
closed after 1.5 s, then the server log checked.
"""
import glob
import json
import os
import time
import urllib.request

BASE = "http://127.0.0.1:1234"
loaded = json.load(urllib.request.urlopen(BASE + "/api/v0/models", timeout=5))
model = next(m["id"] for m in loaded["data"] if m.get("state") == "loaded")


def post(content, max_tokens):
    body = json.dumps({"model": model, "stream": True, "max_tokens": max_tokens,
                       "stream_options": {"include_usage": True},
                       "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=120)


# (1) to the end
keys, finish, usage, chunks, t0 = {}, None, None, 0, time.time()
first_content = None
with post("In one sentence, what is a CPU?", 300) as r:
    for raw in r:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:") or line == "data: [DONE]":
            continue
        d = json.loads(line[5:])
        chunks += 1
        if d.get("usage"):
            usage = d["usage"]
        for ch in d.get("choices", []):
            for k, v in (ch.get("delta") or {}).items():
                if v:
                    keys[k] = keys.get(k, 0) + 1
                    if k == "content" and first_content is None:
                        first_content = round(time.time() - t0, 2)
            if ch.get("finish_reason"):
                finish = ch["finish_reason"]
print(f"(1) chunks={chunks} delta keys={keys} finish_reason={finish} usage={usage} "
      f"first content after {first_content}s, total {time.time() - t0:.1f}s")

# (2) close mid-stream
started = time.strftime("%H:%M:%S")
r = post("Write a 1500-word essay about mountains.", 2000)
t0 = time.time()
got = 0
for raw in r:
    got += 1
    if time.time() - t0 > 1.5:
        break
r.close()
print(f"(2) closed after {time.time() - t0:.2f}s and {got} lines; started {started}")
time.sleep(3)
logs = sorted(glob.glob(os.path.expanduser("~/.lmstudio/server-logs/**/*.log"), recursive=True), key=os.path.getmtime)
tail = open(logs[-1], encoding="utf-8", errors="replace").read().splitlines()[-40:]
for l in [l for l in tail if "cancel" in l.lower() or "disconnect" in l.lower()][-3:]:
    print("   ", l[:180])

# RESULT, 2026-11-18 22:29 (qwen3.8-27b-uncensored-vision, LM Studio):
# (1) chunks=82 delta keys={'role': 1, 'reasoning_content': 56, 'content': 24} finish_reason=stop
#     usage={'prompt_tokens': 61, 'completion_tokens': 84, 'total_tokens': 145,
#            'completion_tokens_details': {'reasoning_tokens': 56}}; first content after 0.88 s, total 1.1 s
# (2) closed after 1.52 s and 239 lines; server log at the same second:
#     "Client disconnected. Stopping generation..." and "srv stop: cancel task, id_task = 165"
# Every prediction held: reasoning and content are separate delta fields
# (reasoning_content), the last chunk carries finish_reason and usage (with
# reasoning_tokens), and a mid-stream close cancels the generation.
