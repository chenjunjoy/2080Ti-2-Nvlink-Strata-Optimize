#!/usr/bin/env bash
# Verify --pipeline-windows 2 on Strata IQ2_XS (port 8080). vLLM + open-webui already stopped.
set -u
KEY="$(cat /srv/share/strata-ops/strata-api-key.txt)"
STRATA=/srv/share/Strata
LOGDIR=/srv/share/strata-ops/logs
BENCH=/srv/share/strata-ops/pipeline-ab.py
CFG=$STRATA/strata-iq2_xs.json
CFG2=$STRATA/strata-iq2_xs.pw2.json
PORT=8080
BASE="http://127.0.0.1:$PORT"
log(){ echo "[$(date '+%T')] $*"; }
gpu_used(){ nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | paste -sd+ | bc; }

stop_strata(){
  pkill -f 'serve/server[.]py' 2>/dev/null || true
  pkill -f 'engine/strata --ser[v]e' 2>/dev/null || true
  for i in $(seq 60); do ss -ltn 2>/dev/null | grep -q ":$PORT" || break; sleep 2; done
  sleep 2
}
wait_strata(){ for i in $(seq 200); do curl -sf -m 2 "$BASE/health" 2>/dev/null | grep -q 'qwen3.8-flash-next-iq2_xs' && return 0; sleep 3; done; return 1; }
start_strata(){ cd "$STRATA"; : > "$STRATA/strata-iq2_xs.log"; nohup .venv/bin/python serve/server.py --engine strata --config "$1" --port "$PORT" >"$LOGDIR/pipeline-server.out" 2>&1 & }

python3 - "$CFG" "$CFG2" <<'PY'
import json, sys
c = json.load(open(sys.argv[1]))
if "--pipeline-windows" not in c["args"]:
    c["args"] += ["--pipeline-windows", "2"]
json.dump(c, open(sys.argv[2], "w"), indent=1)
print("wrote", sys.argv[2])
PY

log "确认 8080 空闲且无 vLLM/open-webui"
ss -ltn 2>/dev/null | grep -q ':8080' && log "警告: 8080 仍被占用" || log "8080 空闲 ✓"

log "ARM A: Strata 基准(默认,无 pipeline)"
stop_strata; start_strata "$CFG"
wait_strata && log "就绪 ✓ (确认模型是 IQ2_XS,不是 vLLM/open-webui)" || log "未就绪"
grep -iE 'pipeline-windows|is off:' "$STRATA/strata-iq2_xs.log" | tail -2 || echo "(无 pipeline 行 = 默认关)"
python3 "$BENCH" baseline "$KEY" "$BASE" 2>&1 | tee "$LOGDIR/pipeline-baseline.txt"

log "ARM B: Strata + --pipeline-windows 2"
stop_strata; start_strata "$CFG2"
wait_strata || log "未就绪"
grep -iE 'pipeline-windows' "$STRATA/strata-iq2_xs.log" | tail -3
python3 "$BENCH" pw2 "$KEY" "$BASE" 2>&1 | tee "$LOGDIR/pipeline-pw2.txt"

log "收尾:保持 Strata 基准配置运行"
stop_strata; start_strata "$CFG"
wait_strata && log "Strata (基准) 运行中 :8080" || log "启动失败"
log "ALL DONE"
