#!/usr/bin/env python3
"""Resumable downloader for the gated OrcaRouter Uncensored IQ3_XXS shards."""
import os, sys, time, urllib.request

TOKEN = open("/srv/share/strata-ops/.hf_token").read().strip()
REPO  = "orcarouter/Qwen3.8-Flash-Next-Uncensored-GGUF"
DEST  = "/srv/share/Strata-data/models/orca-iq3_xxs"
FILES = [
    ("Qwen3.8-Flash-Next-Uncensored-IQ3_XXS-00001-of-00002.gguf", 44637691008),
    ("Qwen3.8-Flash-Next-Uncensored-IQ3_XXS-00002-of-00002.gguf", 40564977024),
    ("mmproj-Qwen3.8-Flash-Next-Uncensored-F16.gguf", 907543296),
]
os.makedirs(DEST, exist_ok=True)

def log(m): print(f"{time.strftime('%H:%M:%S')}  {m}", flush=True)

def download(fn, want):
    path = os.path.join(DEST, fn)
    while True:
        have = os.path.getsize(path) if os.path.exists(path) else 0
        if have >= want:
            log(f"[done] {fn}  {have/1e9:.2f} GB")
            return True
        req = urllib.request.Request(f"https://huggingface.co/{REPO}/resolve/main/{fn}",
                                     headers={"Authorization": "Bearer " + TOKEN})
        if have:
            req.add_header("Range", f"bytes={have}-")
        try:
            t0 = time.time(); last = t0
            with urllib.request.urlopen(req, timeout=120) as r:
                mode = "ab" if (have and r.status == 206) else "wb"
                if mode == "wb":
                    have = 0
                with open(path, mode) as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                        now = time.time()
                        if now - last >= 15:
                            done = f.tell(); el = now - t0
                            bps = (done - have) / el                    # bytes/s
                            rate = bps / (1 << 20)                      # MiB/s
                            left = (want - done) / max(bps, 1) / 60     # minutes
                            log(f"{fn[-18:]}  {done/1e9:.2f}/{want/1e9:.2f} GB  "
                                f"{rate:.1f} MiB/s  ETA {left:.0f} min")
                            last = now
        except Exception as e:
            log(f"[retry] {fn}: {e}")
            time.sleep(6)

ok = all(download(fn, sz) for fn, sz in FILES)
log("ALL DONE" if ok else "INCOMPLETE")
sys.exit(0 if ok else 1)
