#!/usr/bin/env bash
# Speed comparison driver: Strata (IQ2_XS, Orca IQ3_XXS) vs vLLM (TP2 NVLink on/off)
set -u
KEY="$(cat /srv/share/strata-ops/strata-api-key.txt)"
LOGDIR=/srv/share/strata-ops/logs
BENCH=/srv/share/strata-ops/llm-bench.py
R=3
log(){ echo "[$(date '+%T')] $*"; }

gpu_used(){ nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | paste -sd+ | bc; }

stop_all(){
  pkill -f 'serve/server[.]py' 2>/dev/null || true
  pkill -f 'engine/strata --ser[v]e' 2>/dev/null || true
  pkill -f 'vllm[.]entrypoints' 2>/dev/null || true
  for i in $(seq 80); do
    ss -ltn 2>/dev/null | grep -qE ':8080|:8000' && { sleep 3; continue; }
    [ "$(gpu_used)" -lt 800 ] && break
    sleep 3
  done
  sleep 3
}
wait_url(){ for i in $(seq 200); do curl -sf -m 2 "$1" >/dev/null 2>&1 && return 0; sleep 3; done; return 1; }

log "===== ARM1: Strata Orca IQ3_XXS (32K) ====="
wait_url http://127.0.0.1:8080/health || { cd /srv/share/Strata; nohup ./run-orca-iq3_xxs.sh >$LOGDIR/orca-server.out 2>&1 & wait_url http://127.0.0.1:8080/health; }
python3 "$BENCH" "Strata-Orca-IQ3_XXS_32K" http://127.0.0.1:8080 strata "$KEY" $R 2>&1 | tee $LOGDIR/bench-orca.txt

log "===== ARM2: Strata IQ2_XS (128K) ====="
stop_all; cd /srv/share/Strata; nohup ./run-iq2_xs.sh >$LOGDIR/iq2xs-server.out 2>&1 &
wait_url http://127.0.0.1:8080/health || log "IQ2_XS 未就绪"
python3 "$BENCH" "Strata-IQ2_XS_128K" http://127.0.0.1:8080 strata "$KEY" $R 2>&1 | tee $LOGDIR/bench-iq2xs.txt

log "===== ARM3: vLLM 27B TP2 (NVLink on) ====="
stop_all; nohup bash /home/jim/scripts/vllm-run.sh >$LOGDIR/vllm-nvl-on.out 2>&1 &
wait_url http://127.0.0.1:8000/health || log "vLLM(on) 未就绪"
python3 "$BENCH" "vLLM-27B-TP2-NVLink-on" http://127.0.0.1:8000 Qwen3.8-27B-NVFP4 - $R '{"chat_template_kwargs":{"enable_thinking":false}}' 2>&1 | tee $LOGDIR/bench-vllm-on.txt

log "===== ARM4: vLLM 27B TP2 (NVLink off) ====="
stop_all; VLLM_DISABLE_CUSTOM_ALL_REDUCE=1 NCCL_P2P_DISABLE=1 nohup bash /home/jim/scripts/vllm-run.sh >$LOGDIR/vllm-nvl-off.out 2>&1 &
wait_url http://127.0.0.1:8000/health || log "vLLM(off) 未就绪"
python3 "$BENCH" "vLLM-27B-TP2-NVLink-off" http://127.0.0.1:8000 Qwen3.8-27B-NVFP4 - $R '{"chat_template_kwargs":{"enable_thinking":false}}' 2>&1 | tee $LOGDIR/bench-vllm-off.txt

log "===== 恢复 Orca 运行 ====="
stop_all; cd /srv/share/Strata; nohup ./run-orca-iq3_xxs.sh >$LOGDIR/orca-server.out 2>&1 &
wait_url http://127.0.0.1:8080/health || log "Orca 恢复失败"
log "ALL DONE"
