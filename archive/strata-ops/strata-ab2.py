#!/usr/bin/env python3
"""Round 2 A/B: short (~2K) and long (~6K) prompt reads + decode, against tuned baseline."""
import json, copy, os, statistics, subprocess, time, uuid, urllib.request, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CFG  = "/srv/share/Strata/strata-iq2_xs.json"
BASE = os.path.join(HERE, "backups", "strata-iq2_xs.json.tuned")
KEY  = open(os.path.join(HERE, "strata-api-key.txt")).read().strip()
URL  = "http://127.0.0.1:8080/v1/chat/completions"

PARA = ("Retrieval-augmented generation combines a parametric language model with a "
        "non-parametric memory of documents. The retriever ranks passages by relevance, "
        "the generator conditions on them, and the system returns an answer grounded in "
        "the cited evidence. ")
B2K = PARA * 33      # ~2K tokens
B6K = (PARA * 900)[:32000]  # ~6K tokens
Q   = "\n\nIn one short sentence, what is this text about?"

def log(m): print(m, flush=True)

def call(prompt, max_tokens):
    body = json.dumps({"model": "strata", "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "temperature": 0,
                       "reasoning_effort": "none"}).encode()
    req = urllib.request.Request(URL, data=body,
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=900))["timings"]

def stop():
    for pat in ("setup.py --calibrate", "serve/server.py --engine strata", "engine/strata --serve"):
        subprocess.run(f"pkill -f '{pat}'", shell=True)
    for _ in range(60):
        if subprocess.run("ss -ltn 2>/dev/null | grep -q ':8080'", shell=True).returncode != 0:
            break
        time.sleep(2)
    time.sleep(3)

def start():
    subprocess.Popen("cd /srv/share/Strata && nohup ./run-iq2_xs.sh >/srv/share/strata-server.out 2>&1 &", shell=True)
    for _ in range(160):
        try:
            urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=3); return True
        except Exception:
            time.sleep(5)
    return False

def bench(n=3):
    p2 = [call(f"[{uuid.uuid4().hex}] " + B2K + Q, 4).get("prompt_per_second", 0.0) for _ in range(n)]
    p6 = [call(f"[{uuid.uuid4().hex}] " + B6K + Q, 4).get("prompt_per_second", 0.0) for _ in range(n)]
    d  = [call(PARA + Q, 256).get("predicted_per_second", 0.0) for _ in range(n)]
    return statistics.median(p2), statistics.median(p6), statistics.median(d)

def apply_variant(v):
    cfg = json.load(open(BASE))
    for a in v.get("args_add", []):
        cfg["args"].append(a)
    for k, val in v.get("args_set", {}).items():
        i = cfg["args"].index(k); cfg["args"][i + 1] = val
    cfg.update(v.get("set", {}))
    if "env" in v:
        cfg.setdefault("env", {}).update(v["env"])
    json.dump(cfg, open(CFG, "w"), indent=1)

variants = [
    ("prefill_help",   {"env": {"STRATA_PREFILL_HELP": "1"}}),
    ("pf_fused",       {"env": {"STRATA_PF_FUSED": "1"}}),
    ("split_mtp_batch",{"env": {"STRATA_SPLIT_MTP_BATCH": "1"}}),
    ("mtp_batch+fused",{"env": {"STRATA_SPLIT_MTP_BATCH": "1", "STRATA_PF_FUSED": "1"}}),
]

res = {}
log("baseline (tuned)")
stop()
if not start(): log("FATAL"); sys.exit(1)
res["baseline(tuned)"] = bench()
log(f"  baseline: 2K {res['baseline(tuned)'][0]:.1f} | 6K {res['baseline(tuned)'][1]:.1f} | decode {res['baseline(tuned)'][2]:.2f}")

for name, v in variants:
    log(f"variant {name}")
    apply_variant(v); stop()
    if not start(): log(f"  {name}: no server, skip"); continue
    res[name] = bench()
    b = res["baseline(tuned)"]
    log(f"  2K {res[name][0]:.1f} ({(res[name][0]/b[0]-1)*100:+.1f}%) | "
        f"6K {res[name][1]:.1f} ({(res[name][1]/b[1]-1)*100:+.1f}%) | "
        f"decode {res[name][2]:.2f} ({(res[name][2]/b[2]-1)*100:+.1f}%)")

subprocess.run(f"cp -a {BASE} {CFG}", shell=True)
log("restored tuned baseline; restarting")
stop(); start()

log("\n=== ROUND 2 SUMMARY (median of 3) ===")
log(f"{'variant':18s} {'2K':>9s} {'6K':>9s} {'decode':>9s}")
for k, (a, b, c) in res.items():
    log(f"{k:18s} {a:9.1f} {b:9.1f} {c:9.2f}")
json.dump({k: {"p2k": v[0], "p6k": v[1], "decode": v[2]} for k, v in res.items()},
          open(os.path.join(HERE, "results", "strata-ab2-results.json"), "w"), indent=1)
