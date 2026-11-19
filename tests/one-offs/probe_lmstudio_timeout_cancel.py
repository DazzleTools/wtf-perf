"""probe_lmstudio_timeout_cancel.py -- phase M measurement (a), licensed 2026-11-18.

Question: when a NON-streamed chat request (stream:false, as the AI library's
openai_compat transport sends) is abandoned by a client timeout, does LM Studio
cancel the generation? The library's openai_compat.py line 29 says it does not;
the tag-manager design measured cancellation for a STREAMED request closed by
the client.

Prediction written before running: the server log shows "cancel task" within a
second or two of the client giving up (the C# measurement saw 0.4 s for a stream).

Method: POST a long generation with a 2 s urllib timeout to the loaded model,
note the wall time, then read the newest LM Studio server log for lines after
the request started.
"""
import glob
import json
import os
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:1234"
loaded = json.load(urllib.request.urlopen(BASE + "/api/v0/models", timeout=5))
model = next(m["id"] for m in loaded["data"] if m.get("state") == "loaded")
body = json.dumps({"model": model, "stream": False, "max_tokens": 2000, "reasoning_effort": "none",
                   "messages": [{"role": "user", "content": "Write a 1500-word essay about rivers."}]}).encode()
req = urllib.request.Request(BASE + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
t0 = time.time()
started = time.strftime("%Y-%m-%d %H:%M:%S")
try:
    urllib.request.urlopen(req, timeout=2)
    print("request COMPLETED within 2 s (no timeout happened)")
except Exception as e:  # socket.timeout / URLError
    print(f"client gave up after {time.time() - t0:.2f} s: {type(e).__name__}")
time.sleep(4)
logs = sorted(glob.glob(os.path.expanduser("~/.lmstudio/server-logs/**/*.log"), recursive=True), key=os.path.getmtime)
print("model:", model, "| started:", started, "| newest log:", logs[-1] if logs else None)
if logs:
    tail = open(logs[-1], encoding="utf-8", errors="replace").read().splitlines()[-60:]
    hits = [l for l in tail if "cancel" in l.lower() or "disconnect" in l.lower() or "abort" in l.lower()]
    print("cancel/abort/disconnect lines in the last 60:", len(hits))
    for l in hits[-6:]:
        print("  ", l[:200])

# RESULT, 2026-11-18 21:58 (qwen3.8-27b-uncensored-vision, LM Studio, stream:false, 2 s client timeout):
#   client gave up after 2.02 s: TimeoutError
#   [2026-11-18 21:58:02][INFO][LM STUDIO SERVER] Client disconnected. Stopping generation...
#     (If the model is busy processing the prompt, it will finish first.)
#   [2026-11-18 21:58:02][DEBUG] ... srv stop: cancel task, id_task = 0
# Prediction held: LM Studio cancels a non-streamed generation when the client times out.
# The AI library's openai_compat.py line 29 ("a client timeout does not cancel
# server-side work") is wrong for LM Studio; prompt processing already under way finishes first.
