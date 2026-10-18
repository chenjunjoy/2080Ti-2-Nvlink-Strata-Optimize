#!/usr/bin/env python3
"""A/B test single-request speed of candidate engine settings against the tuned baseline.

For each variant: apply it to a copy of the tuned config, restart the server, run the
benchmark, record medians. Restores the tuned config at the end."""
import json, copy, os, statistics, subprocess, time, urllib.request, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CFG  = "/srv/share/Strata/strata-iq2_xs.json"
BASE = os.path.join(HERE, "backups", "strata-iq2_xs.json.tuned")
KEY  = open(os.path.join(HERE, "strata-api-key.txt")).read().strip()
URL  = "http://127.0.0.1:8080/v1/chat/completions"

PARA = ("Retrieval-augmented generation combines a parametric language model with a "
        "non-parametric memory of documents. The retriever ranks passages by relevance, "
        "the generator conditions on them, and the system returns an answer grounded in "
        "the cited evidence. ")
BODY = (PARA * 900)[:32000]
Q    = "\n\nIn one short sentence, what is this text about?"

def log(m): print(m, flush=True)

def call(prompt, max_tokens):
    body = json.dumps({"model": "strata", "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "temperature": 0,
                       "reasoning_effort": "none"}).encode()
    import uuid
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
    subprocess.Popen("cd /srv/share/Strata && nohup ./run-iq2_xs.sh >/srv/share/strata-server.out 2>&1 &",
                     shell=True)
    for _ in range(160):
        try:
            urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=3)
            return True
        except Exception:
            time.sleep(5)
    return False

def bench(n=3):
    d = [call(PARA + Q, 256).get("predicted_per_second", 0.0) for _ in range(n)]
    import uuid
    p = [call(f"[{uuid.uuid4().hex}] " + BODY + Q, 4).get("prompt_per_second", 0.0) for _ in range(n)]
    return statistics.median(p), statistics.median(d)

def apply_variant(v):
    cfg = json.load(open(BASE))
    for a in v.get("args_add", []):
        cfg["args"].append(a)
    for k, val in v.get("args_set", {}).items():
        i = cfg["args"].index(k); cfg["args"][i + 1] = val
    for k, val in v.get("set", {}).items():
        cfg[k] = val
    if "env" in v:
        cfg.setdefault("env", {}).update(v["env"])
    json.dump(cfg, open(CFG, "w"), indent=1)

variants = [
    ("layer_split_20",    {"set": {"layer_split": "20"}}),
    ("prefill_help",      {"env": {"STRATA_PREFILL_HELP": "1"}}),
    ("pipeline_windows_2",{"args_add": ["--pipeline-windows", "2"]}),
    ("split_mtp_batch",   {"env": {"STRATA_SPLIT_MTP_BATCH": "1"}}),
    ("kv_k8v4",           {"args_set": {"--kv": "k8v4"}}),
]

results = {}
log("baseline (tuned) — measuring")
stop()
if not start(): log("FATAL: baseline server did not come up"); sys.exit(1)
bp, bd = bench()
results["baseline(tuned)"] = (bp, bd)
log(f"  baseline: prefill {bp:.1f} | decode {bd:.2f}")

for name, v in variants:
    log(f"variant {name} — applying + restart")
    apply_variant(v)
    stop()
    if not start():
        log(f"  {name}: server did not come up, skipping")
        continue
    pp, dd = bench()
    results[name] = (pp, dd)
    log(f"  {name}: prefill {pp:.1f} ({(pp/bp-1)*100:+.1f}%) | decode {dd:.2f} ({(dd/bd-1)*100:+.1f}%)")

# restore tuned baseline and start it
subprocess.run(f"cp -a {BASE} {CFG}", shell=True)
log("restored tuned baseline config; restarting")
stop()
start()

log("\n=== SUMMARY (median of 3) ===")
log(f"{'variant':20s} {'prefill tok/s':>14s} {'decode tok/s':>13s}")
for k, (p, d) in results.items():
    log(f"{k:20s} {p:14.1f} {d:13.2f}")
json.dump({k: {"prefill": v[0], "decode": v[1]} for k, v in results.items()},
          open(os.path.join(HERE, "results", "strata-ab-results.json"), "w"), indent=1)
