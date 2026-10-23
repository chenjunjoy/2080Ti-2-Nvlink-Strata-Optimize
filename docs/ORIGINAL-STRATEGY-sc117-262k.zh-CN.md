# 原始策略：SC117 IQ3_XXS · 262K · 双 RTX 2080Ti（优化前快照）

> 保存日期：2026-10-23
> 用途：保留 2026-10-23 优化前的完整运行策略，便于对比、回滚和复现基线。
> 对应优化复盘：[`../README.md`](../README.md) §9
> 原始配置备份：`/srv/share/strata-ops/backups/strata-sc117-iq3_xxs.json.pre-opt-20261023-142008`

---

## 1. 策略一句话

48 层 MoE 模型按 `layer_split: 20` 切到两张 22G 卡，262144 上下文，INT8 KV + 32768 cells 常驻，MTP 投机 4 token，8K prompt chunk，视觉走 GPU；**不启用** BF16 张量核、QSA SIMT、pipeline windows 和会话停车缓存。

## 2. 原始配置（完整，API key 已脱敏）

```json
{
 "exe": "/srv/share/Strata/engine/strata",
 "args": [
  "--pack", "/srv/share/Strata-data/packs/sc117-iq3_xxs",
  "--native", "/srv/share/Strata-data/models/sc117-iq3_xxs/IQ3_XXS/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_XXS-00001-of-00002.gguf",
  "--ple-gguf", "/srv/share/Strata-data/models/sc117-iq3_xxs/IQ3_XXS/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_XXS-00002-of-00002.gguf",
  "--expert-profile", "/srv/share/Strata/data/expert-profile.bin",
  "--expert-cache", "auto",
  "--prefill", "auto",
  "--spec", "4",
  "--spec-min-p", "0.70",
  "--mtp", "/srv/share/Strata-data/mtp/rt",
  "--mtp-hnorm", "stream",
  "--short-read", "32",
  "--max-context", "262144",
  "--kv", "int8",
  "--kv-resident", "32768",
  "--vision",
  "--pcie-frac", "1.00",
  "--vram-reserve-mib", "1024"
 ],
 "cwd": "/srv/share/Strata",
 "tokenizer": "/srv/share/Strata-data/packs/sc117-iq3_xxs/tokenizer",
 "model_name": "sc117-qwen3.8-flash-next-abliterated-iq3_xxs",
 "log": "/srv/share/Strata/strata-sc117-iq3_xxs.log",
 "lib_dirs": [
  "/usr/local/cuda-13.0/bin",
  "/usr/local/cuda-13.0/lib64"
 ],
 "port": 8080,
 "gpu": [0, 1],
 "gpus_asked": true,
 "layer_split": "20",
 "host": "0.0.0.0",
 "api_key": "<REDACTED>",
 "reasoning_effort": "none",
 "vision": {
  "exe": "/srv/share/Strata/engine/strata-vision",
  "mmproj": "/srv/share/Strata-data/models/sc117-iq3_xxs/mmproj-Qwen3.8-Flash-Next-BF16.gguf",
  "model": "/srv/share/Strata-data/models/sc117-iq3_xxs/IQ3_XXS/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_XXS-00001-of-00002.gguf",
  "gpu": true,
  "max_tokens": 1024
 },
 "env": {
  "STRATA_SPLIT_MTP_BATCH": "1"
 }
}
```

## 3. 原始参数说明

| 参数 | 原值 | 当时的用意 |
|---|---|---|
| `layer_split` | `20` | 第 2 张卡从第 20 层开始；此前手工/自动搜索留下的值 |
| `--prefill` | `auto` | 引擎按专家缓存可借额度选 chunk，本机落到 **8192** |
| `--spec` / `--spec-min-p` | `4` / `0.70` | MTP 草稿 4 token，提议阈值 0.70 |
| `--mtp` / `--mtp-hnorm` | `.../mtp/rt` / `stream` | 草稿层与逐流 norm |
| `--short-read` | `32` | 短文本增量走 decode 窗口 |
| `--max-context` | `262144` | 256K 风险档 |
| `--kv` / `--kv-resident` | `int8` / `32768` | KV 量化 + 每 QSA 层 32768 cells 常驻 |
| `--expert-cache` | `auto` | 参考机落在约 10240 + 8004 slots |
| `--vram-reserve-mib` | `1024` | 视觉/余量预留 |
| `--pcie-frac` | `1.00` | 按本机 PCIe 实测标定 |
| vision | `gpu: true` | 视觉编码器走 GPU |
| `reasoning_effort` | `none` | 服务默认关思考 |
| env | `STRATA_SPLIT_MTP_BATCH=1` | 层切分下 MTP 草稿批处理 |

未设置的开关（优化后才加入）：`STRATA_BF16_TC`、`STRATA_SELECT_SIMT`、`STRATA_PREFILL_HELP`、`--pipeline-windows`、`--conversation-cache-*`。

## 4. 原始基线数字

测试条件：同机、262144 上下文、单请求、greedy、`reasoning_effort: none`、每次唯一 prompt 避开缓存、8K chunk、split 20。

| 项目 | 原始结果 |
|---|---:|
| 6.0K prefill | 901.0 tok/s |
| 23.8K prefill | 1345.3 tok/s |
| 89.2K prefill | 1467.3 tok/s |
| decode（256 token，2 次） | 74.3 tok/s（69.7 / 78.8） |

原始日志：`/srv/share/Strata/strata-sc117-iq3_xxs.log`（优化前启动记录）
原始基准输出：`/srv/share/Strata-optimize/results/2026-10-23-iq3_xxs-262k/bench-baseline-v2.txt`

## 5. 原始启动方式

```bash
cd /srv/share/Strata
nohup .venv/bin/python serve/server.py \
  --engine strata \
  --config /srv/share/Strata/strata-sc117-iq3_xxs.json \
  --port 8080 > /tmp/strata-sc117.out 2>&1 &
```

- API：`http://127.0.0.1:8080/v1`，需要 key（原 key 不写入本文件）。
- 该配置没有 systemd 单元，手工启动；`run-sc117-iq3_xxs.sh` 可作入口。

## 6. 回滚到原始策略

```bash
# 1) 停当前服务
pkill -TERM -f 'strata-sc117-iq3_xxs.json'

# 2) 恢复原始配置
cp /srv/share/strata-ops/backups/strata-sc117-iq3_xxs.json.pre-opt-20261023-142008 \
   /srv/share/Strata/strata-sc117-iq3_xxs.json

# 3) 重新启动
cd /srv/share/Strata
nohup .venv/bin/python serve/server.py \
  --engine strata --config /srv/share/Strata/strata-sc117-iq3_xxs.json --port 8080 \
  > /tmp/strata-sc117.out 2>&1 &
```

> 注意：`pkill -f` 的模式不要包含 `serve/server.py`，否则可能匹配到执行命令的 shell 自身；更稳妥的是先 `pgrep -af strata-sc117` 再按 PID 停止。

## 7. 参考文档原始策略（摘要）

本次优化参考的是《Strata 部署指南：Qwen3.8-Flash-Next（IQ3_S）· 双 RTX 2080Ti 22G》（2026-10-12，引擎 v0.1.43 + sm_75 批次补丁）。其核心策略：

- 权重 IQ3_S 双分片，262144 上下文，MTP `--spec 4 --spec-min-p 0.70`
- 双卡层切分 `--layer-split 26`，`--prefill auto:16384`
- `--pipeline-windows 2`，`--kv int8 --kv-resident 32768`
- `--conversation-cache-mib 16384 --conversation-cache-slots 12`
- 视觉编码器走 CPU，`--vram-reserve-mib 700`
- env：`STRATA_BF16_TC=1`、`STRATA_SELECT_SIMT=2`、`STRATA_PA_V2T=1`、`STRATA_REFILL_PARTS=1`、`STRATA_PREFILL_HELP=1`
- 9 个 sm_75 PR 用 cherry-pick 叠加在 v0.1.43 上

本机实际采用的是其中能在 0.1.44.1 上生效、且经本机 A/B 验证的部分；未照抄项与差异见 [`../README.md`](../README.md) §9.4–§9.5。

参考文档原文存档：[`../reference/Qwen3.8-Flash-Next-IQ3_S-dual-2080Ti-262K-deploy-guide.zh-CN.md`](../reference/Qwen3.8-Flash-Next-IQ3_S-dual-2080Ti-262K-deploy-guide.zh-CN.md)。

## 8. 与优化后策略的差异

| 项 | 原始 | 优化后 |
|---|---|---|
| layer split | 20 | 24 |
| BF16 张量核 / QSA SIMT / prefill help | 未设 | 全部开启 |
| pipeline windows | 关 | 2 |
| 会话停车缓存 | 关 | 4096 MiB / 8 / min-tokens 2048 |
| prefill chunk | 8K | 8K（未改） |
| 上下文 / KV / 视觉 | 262K / int8+32768 / GPU | 不变 |

完整优化后配置：[`../configs/strata-sc117-iq3_xxs.json`](../configs/strata-sc117-iq3_xxs.json)
