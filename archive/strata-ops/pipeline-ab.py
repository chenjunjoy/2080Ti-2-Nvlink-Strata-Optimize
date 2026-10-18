#!/usr/bin/env python3
"""A/B for --pipeline-windows: decode + 6K prefill + 16K prefill (unique prompts)."""
import json, sys, time, statistics, uuid, urllib.request

label = sys.argv[1]
KEY = sys.argv[2]
base = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8080"
URL = base.rstrip("/") + "/v1/chat/completions"

PARA = ("Retrieval-augmented generation combines a parametric language model with a "
        "non-parametric memory of documents. The retriever ranks passages by relevance, "
        "the generator conditions on them, and the system returns an answer grounded in "
        "the cited evidence. ")
P6K = PARA * 128
P16K = PARA * 340
Q = "\n\nIn one short sentence, what is this text about?"
DECODE = ("Write a detailed technical explanation of how a transformer neural network "
          "processes text, covering tokenization, self-attention and autoregressive "
          "generation. Aim for about 300 words.")

def call(prompt, mt):
    body = json.dumps({"model": "strata", "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": mt, "temperature": 0, "reasoning_effort": "none"}).encode()
    req = urllib.request.Request(URL, data=body,
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=1200))["timings"]

print(f"=== {label} ===")
d = [call(DECODE, 256)["predicted_per_second"] for _ in range(3)]
p6 = [call(f"[{uuid.uuid4().hex}] " + P6K + Q, 2)["prompt_per_second"] for _ in range(3)]
p16 = [call(f"[{uuid.uuid4().hex}] " + P16K + Q, 2)["prompt_per_second"] for _ in range(2)]
print(f"  decode   : {statistics.median(d):6.2f} tok/s   ({', '.join(f'{x:.1f}' for x in d)})")
print(f"  prefill 6K : {statistics.median(p6):6.1f} tok/s ({', '.join(f'{x:.0f}' for x in p6)})")
print(f"  prefill 16K: {statistics.median(p16):6.1f} tok/s ({', '.join(f'{x:.0f}' for x in p16)})")
print(f"[{label}] decode {statistics.median(d):.2f} | p6K {statistics.median(p6):.0f} | p16K {statistics.median(p16):.0f}")
