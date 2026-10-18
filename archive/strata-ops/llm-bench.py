#!/usr/bin/env python3
"""Streaming single-request benchmark, usable for any OpenAI-compatible server.

  python3 llm-bench.py <label> <base_url> <model> [api_key] [runs] [extra_json]

Measures per run: TTFT, decode tok/s (uses the server-reported completion_tokens
when available, so servers that coalesce several tokens into one SSE chunk are
counted correctly), and TTFT on a ~6K-token unique (cache-busting) prompt.
"""
import json, sys, time, statistics, uuid, urllib.request

def stream_call(url, model, key, prompt, max_tokens, extra=None, want_usage=True):
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "max_tokens": max_tokens, "temperature": 0,
               "reasoning_effort": "none", "stream": True}
    if want_usage:
        payload["stream_options"] = {"include_usage": True}
    if extra:
        payload.update(extra)
    hdr = {"Content-Type": "application/json"}
    if key:
        hdr["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=hdr)
    try:
        resp = urllib.request.urlopen(req, timeout=1800)
    except urllib.error.HTTPError:
        if want_usage:                      # server rejects stream_options -> retry without
            return stream_call(url, model, key, prompt, max_tokens, extra, want_usage=False)
        raise
    t0 = time.time(); first = last = None; n = 0; ct = None
    with resp:
        for raw in resp:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            d = line[5:].strip()
            if d == "[DONE]":
                break
            try:
                o = json.loads(d)
            except Exception:
                continue
            u = o.get("usage")
            if u and u.get("completion_tokens"):
                ct = u["completion_tokens"]
            ch = o.get("choices") or []
            if ch and (ch[0].get("delta") or {}).get("content"):
                now = time.time()
                if first is None:
                    first = now
                last = now; n += 1
    return (first - t0 if first else None), (last - first if first and last else None), n, ct

PARA = ("Retrieval-augmented generation combines a parametric language model with a "
        "non-parametric memory of documents. The retriever ranks passages by relevance, "
        "the generator conditions on them, and the system returns an answer grounded in "
        "the cited evidence. ")
B6K = (PARA * 900)[:32000]
Q = "\n\nIn one short sentence, what is this text about?"
DECODE = ("Write a detailed technical explanation of how a transformer neural network "
          "processes text, covering tokenization, self-attention and autoregressive "
          "generation. Aim for about 300 words.")

def main():
    label, base, model = sys.argv[1], sys.argv[2], sys.argv[3]
    key = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] not in ("", "-") else ""
    runs = int(sys.argv[5]) if len(sys.argv) > 5 else 3
    extra = json.loads(sys.argv[6]) if len(sys.argv) > 6 else None
    url = base.rstrip("/") + "/v1/chat/completions"

    def one(prompt, mt):
        ttft, span, n, ct = stream_call(url, model, key, prompt, mt, extra)
        toks = ct if ct else n
        rate = (toks - 1) / span if span and toks > 1 else 0.0
        return ttft, rate, toks, n

    ttfts, tps = [], []
    for i in range(runs):
        ttft, rate, toks, n = one(DECODE, 256)
        ttfts.append(ttft * 1000); tps.append(rate)
        note = "" if toks == n else f" (server tokens in {n} chunks)"
        print(f"  decode run{i+1}: TTFT {ttft*1000:7.0f} ms | {rate:6.2f} tok/s | {toks} tokens{note}")
    pre = []
    for i in range(runs):
        ttft, rate, toks, n = one(f"[{uuid.uuid4().hex}] " + B6K + Q, 2)
        pre.append(ttft)
        print(f"  prefill run{i+1}: TTFT {ttft:6.2f} s  (~6K-token cold prompt)")
    print(f"[{label}] decode {statistics.median(tps):.2f} tok/s | "
          f"TTFT {statistics.median(ttfts):.0f} ms | 6K-prompt TTFT {statistics.median(pre):.2f} s")

main()
