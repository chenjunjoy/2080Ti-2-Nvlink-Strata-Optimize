#!/usr/bin/env python3
"""Single-request speed benchmark for the local Strata server.

  decode : short prompt, 256 generated tokens        -> decode tok/s
  prefill: ~6K-token prompt (unique each run), 4 out -> prompt tok/s (cold, cache-busting)
Prints each run and the median."""
import json, os, statistics, uuid, urllib.request, sys

URL = "http://127.0.0.1:8080/v1/chat/completions"
HERE = os.path.dirname(os.path.abspath(__file__))
KEY = open(os.path.join(HERE, "strata-api-key.txt")).read().strip()

PARA = ("Retrieval-augmented generation combines a parametric language model with a "
        "non-parametric memory of documents. The retriever ranks passages by relevance, "
        "the generator conditions on them, and the system returns an answer grounded in "
        "the cited evidence. ")
BODY = (PARA * 900)[:32000]
Q = "\n\nIn one short sentence, what is this text about?"

def call(prompt, max_tokens):
    body = json.dumps({"model": "strata", "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "temperature": 0,
                       "reasoning_effort": "none"}).encode()
    req = urllib.request.Request(URL, data=body,
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=900))["timings"]

def bench(name, make_prompt, max_tokens, n):
    rows = [call(make_prompt(), max_tokens) for _ in range(n)]
    p = [x.get("prompt_per_second", 0.0) for x in rows]
    d = [x.get("predicted_per_second", 0.0) for x in rows]
    pn = [x.get("prompt_n", 0) for x in rows]
    for i, x in enumerate(rows, 1):
        print(f"  run{i}: prompt_n={x.get('prompt_n',0):5d} prompt {x.get('prompt_per_second',0):9.1f} tok/s | decode {x.get('predicted_per_second',0):6.2f} tok/s")
    print(f"[{name}] median: prompt_n={statistics.median(pn):.0f} prompt {statistics.median(p):.1f} tok/s | decode {statistics.median(d):.2f} tok/s")

label = sys.argv[1] if len(sys.argv) > 1 else "run"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
print(f"=== {label} ===")
bench("decode ", lambda: PARA + Q, 256, n)
bench("prefill", lambda: f"[{uuid.uuid4().hex}] " + BODY + Q, 4, n)
