#!/usr/bin/env python3
"""Quality comparison: send the same prompts to an OpenAI-compatible server.

  python3 quality-bench.py <label> <base_url> <model> [api_key] [extra_json]
Writes results/quality-<label>.json and prints the answers."""
import json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPTS = [
    ("math",
     "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. "
     "How much does the ball cost? Also, if 5 machines take 5 minutes to make 5 widgets, "
     "how long would 100 machines take to make 100 widgets? Give the two answers."),
    ("lis_code",
     "Write a Python function named solve(nums) that returns the length of the longest "
     "strictly increasing subsequence of the list nums. Return only the code, no explanation."),
    ("moE_zh",
     "用中文简要解释:什么是混合专家(MoE)大模型?它是如何在基本不增加计算量的前提下"
     "大幅扩大参数规模的?请控制在 200 字以内。"),
    ("instr",
     "List exactly 3 advantages and 3 disadvantages of working from home. "
     "Each line must start with '+' or '-', and each line must be at most 8 words. "
     "Output only the 6 lines, nothing else."),
    ("chicken_rabbit",
     "A farmer has chickens and rabbits in a pen. There are 35 heads and 94 legs in total. "
     "How many chickens and how many rabbits are there? Give the two numbers."),
    ("two_sum",
     "Write a Python function named two_sum(nums, target) that returns a list with the "
     "indices of the two numbers that add up to target. Assume exactly one solution exists. "
     "Return only the code, no explanation."),
]

def main():
    label, base, model = sys.argv[1], sys.argv[2], sys.argv[3]
    key = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] not in ("", "-") else ""
    extra = json.loads(sys.argv[5]) if len(sys.argv) > 5 else {}
    url = base.rstrip("/") + "/v1/chat/completions"
    out = {}
    for pid, prompt in PROMPTS:
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
                   "max_tokens": 900, "temperature": 0, "reasoning_effort": "none"}
        payload.update(extra)
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": "Bearer " + key} if key else {})})
        t = time.time()
        r = json.load(urllib.request.urlopen(req, timeout=900))
        el = time.time() - t
        msg = r["choices"][0]["message"]
        ans = (msg.get("content") or "").strip()
        out[pid] = {"answer": ans, "secs": round(el, 2),
                    "completion_tokens": r.get("usage", {}).get("completion_tokens")}
        print(f"\n########## [{label}] {pid}  ({el:.1f}s, {out[pid]['completion_tokens']} tok) ##########")
        print(ans)
    outdir = os.path.join(HERE, "results", time.strftime("%Y-%m-%d"))
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, f"quality-{label}.json")
    json.dump(out, open(path, "w"), ensure_ascii=False, indent=1)
    print(f"\n[saved] {path}")

main()
