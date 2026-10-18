#!/usr/bin/env bash
# Phase 2: same --pipeline-windows A/B on the UNCENSORED model (Strata Orca IQ3_XXS).
# Waits for phase 1 (IQ2_XS, pid 30370) to finish first.
set -u
KEY="$(cat /srv/share/strata-ops/strata-api-key.txt)"
STRATA=/srv/share/Strata
LOGDIR=/srv/share/strata-ops/logs
BENCH=/srv/share/strata-ops/pipeline-ab.py
CFG=$STRATA/strata-orca-iq3_xxs.json
CFG2=$STRATA/strata-orca-iq3_xxs.pw2.json
PORT=8080
BASE="http://127.0.0.1:$PORT"
log(){ echo "[$(date '+%T')] $*"; }

stop_strata(){
  pkill -f 'serve/server[.]py' 2>/dev/null || true
  pkill -f 'engine/strata --ser[v]e' 2>/dev/null || true
  for i in $(seq 60); do ss -ltn 2>/dev/null | grep -q ":$PORT" || break; sleep 2; done
  sleep 2
}
wait_orca(){ for i in $(seq 240); do curl -sf -m 2 "$BASE/health" 2>/dev/null | grep -q 'uncensored' && return 0; sleep 3; done; return 1; }
start_strata(){ cd "$STRATA"; : > "$STRATA/strata-orca-iq3_xxs.log"; nohup .venv/bin/python serve/server.py --engine strata --config "$1" --port "$PORT" >"$LOGDIR/pipeline-orca-server.out" 2>&1 & }

log "等待 IQ2_XS 阶段(pid 30370)结束..."
while kill -0 30370 2>/dev/null; do sleep 30; done
log "第二阶段开始:Orca 无审查版 (IQ3_XXS)"

python3 - "$CFG" "$CFG2" <<'PY'
import json, sys
c = json.load(open(sys.argv[1]))
if "--pipeline-windows" not in c["args"]:
    c["args"] += ["--pipeline-windows", "2"]
json.dump(c, open(sys.argv[2], "w"), indent=1)
print("wrote", sys.argv[2])
PY

log "ARM A: Orca 基准(无 pipeline)"
stop_strata; start_strata "$CFG"
wait_orca && log "就绪 ✓ (uncensored)" || log "未就绪"
python3 "$BENCH" orca-baseline "$KEY" "$BASE" 2>&1 | tee "$LOGDIR/pipeline-orca-baseline.txt"

log "ARM B: Orca + --pipeline-windows 2"
stop_strata; start_strata "$CFG2"
wait_orca || log "未就绪"
grep -iE 'pipeline-windows' "$STRATA/strata-orca-iq3_xxs.log" | tail -3
python3 "$BENCH" orca-pw2 "$KEY" "$BASE" 2>&1 | tee "$LOGDIR/pipeline-orca-pw2.txt"

log "收尾:保持 Orca 基准运行"
stop_strata; start_strata "$CFG"
wait_orca && log "Orca (基准) 运行中 :8080" || log "启动失败"
log "ALL DONE"
