# Strata @ 2×RTX 2080 Ti + NVLink —— 优化复盘

> 硬件：2 × RTX 2080 Ti 22GB（NVLink NV2，2 × 25.781 GB/s），76 GB 内存，PCIe 3.0 x8（本机实测 host↔device 约 6.0–6.2 GB/s）
> 软件：Strata（llama.cpp 系 C++ 推理引擎）+ Python server；CUDA 13.0；`/srv/share/Strata`
> 模型：`Qwen3.8-Flash-Next IQ2_XS`（125B MoE，131072 context）、`OrcaRouter Uncensored IQ3_XXS`（125B MoE 微调）
> 整理日期：2026-10-19
> 依据：`/srv/share/strata-ops` 的文档、日志、基准结果与配置备份（本文不重复贴原始日志）

---

## 0. TL;DR

1. **校准 + 环境变量 + Orca prefill 修复**带来了主要收益：
   - 单请求 decode **82.7 → 87.8 tok/s（+6.2%）**
   - 6K prefill **881.6 → 910.0 tok/s（+3.2%）**
   - Orca 6K 提示读取 **21.6 s → 6.72 s（快 3.2×）**
2. **`--pipeline-windows 2` 经严格 A/B 验证为 +3.9% decode**（两个模型同向，prefill 持平），但**当前生产配置并未启用**，只存在于 `.pw2.json` 变体（见 §3）。
3. **Strata 用不到 NVLink**：层并行（layer split）不是张量并行，无 P2P/AllReduce，验证窗口之间只传几百 KB 激活，走 PCIe ~6 GB/s 即可。
4. **负载选型**：Strata IQ2_XS 生成快（84 tok/s、125B）；vLLM 27B 长提示读取更快（6K 4.66 s）且吃 NVLink；无审查的 vLLM 27B + DFlash2 生成最快（93.7 tok/s）。
5. **质量**：6 道基准题 Strata(125B IQ2_XS) 与 vLLM(27B NVFP4) **全部打平**。
6. **2026-10-23 更新**：按 Qwen3.8 IQ3_S 双 2080Ti 指南重调 262K（SC117 IQ3_XXS）配置：prefill **+18% / +30% / +50%**（6K / 24K / 89K），decode **+8–13%**，针召回 12/12。详见 §9。

---

## 1. 优化清单（已生效）

### 1.1 硬件校准：`--calibrate` → `--pcie-frac` / `--spec-min-p`
- 用引擎自带 `--calibrate` 实测本机 PCIe 与投机解码参数，选定：
  - `--pcie-frac 1.00`
  - `--spec-min-p 0.70`（IQ2_XS；Orca 保持 `0.5`）
- 作用：让层切分/预取按真实链路定价，投机解码的门槛更贴合本机接受率。

### 1.2 `STRATA_SPLIT_MTP_BATCH=1`
- 写入 IQ2_XS 配置的 `env`。
- 效果（官方说明 + 本机复测）：**prefill +3%**。

### 1.3 Orca 预填充分块：`--prefill 512` → `--prefill auto`
- 按官方 `docs/ORCA.md` 的 `--prefill 512` 会把 6K 提示拖到 **21.6 s**。
- 改为 `auto` 后 **6.72 s（3.2×）**，与 IQ2_XS 持平。

### 1.4 Orca 上下文：32K → 131072
- 2026-10-18 将 `--max-context` 从 `32768` 提升到 `131072`（备份 `.pre-128k-*`）。
- 未记录正式 A/B；属于能力扩展，不是速度优化。

### 1.5 `reasoning_effort: "none"`
- 2026-10-18 在两份生产配置中加入，关闭思考前缀（减少无意义输出、降低 TTFT/总时长）。
- 基准方法学中一直使用 greedy + 关闭思考，此次把它固化为服务默认。

### 1.6 最终生产配置（关键参数）

| 参数 | IQ2_XS | Orca IQ3_XXS |
|---|---|---|
| `--expert-cache` | auto | auto |
| `--prefill` | auto | auto |
| `--spec` | 4 | 4 |
| `--spec-min-p` | **0.70** | 0.5 |
| `--pcie-frac` | **1.00** | —（自动） |
| `--max-context` | 131072 | **131072**（原 32768） |
| `--kv` | int8 | int8 |
| `--kv-resident` | 32768 | — |
| `--vram-reserve-mib` | 700 | 700 |
| `layer_split` | auto | auto |
| `reasoning_effort` | **none** | **none** |
| `env` | `STRATA_SPLIT_MTP_BATCH=1` | — |

> 配置文件：`/srv/share/Strata/strata-iq2_xs.json`、`strata-orca-iq3_xxs.json`
> 服务：`strata.service`（IQ2_XS / 8080）、`strata-orca.service`（Orca / 8080），互斥且都不开机自启。

---

## 2. 实测数据

### 2.1 调优前后（单请求）

| 指标 | 调优前 | 调优后 | 变化 |
|---|---:|---:|---:|
| decode | 82.7 tok/s | **87.8 tok/s** | **+6.2%** |
| prefill 6K | 881.6 tok/s | **910.0 tok/s** | **+3.2%** |

### 2.2 `--pipeline-windows 2` 严格 A/B（2026-10-17）

方法：同模型、同两张卡，只改 `--pipeline-windows`；greedy、`reasoning_effort=none`、逐次唯一提示避开缓存；decode 256 token；prefill 6K / 16K；各取中位数。

| 模型 | 指标 | 基准（关） | `--pipeline-windows 2` | 变化 |
|---|---|---:|---:|---:|
| IQ2_XS | decode | 84.80 | **88.10** | **+3.9%** |
| IQ2_XS | prefill 6K | 912.7 | 903.4 | −1.0% |
| IQ2_XS | prefill 16K | 1269.1 | 1265.7 | −0.3% |
| Orca | decode | 71.60 | **74.40** | **+3.9%** |
| Orca | prefill 6K | 884.3 | 888.3 | +0.5% |
| Orca | prefill 16K | 1180.7 | 1177.8 | −0.2% |

- 代价：每卡少 **272 MiB** 专家缓存（官方称 160 MiB；本机实测 272 MiB）。
- 官方文档：AMD RDNA4 默认开、**NVIDIA 默认关**；官方 2×3090 是 **prefill +16.6%、decode 持平**；本机相反（decode +3.9%、prefill 持平），原因是瓶颈落在不同环节。
- **更正**：更早一次 A/B 的"decode −10.8%"是测量噪声，已被本次严格 A/B 推翻，旧结论作废。

### 2.3 与 vLLM 对比（2026-10-17）

| 服务 · 模型 | decode | TTFT | 6K 提示读取 |
|---|---:|---:|---:|
| **Strata · IQ2_XS（125B）** | **84.3 tok/s** | 78 ms | 6.61 s |
| Strata · Orca IQ3_XXS（125B） | 69.6 tok/s | 86 ms | 6.72 s |
| vLLM · 27B NVFP4（NVLink 开） | 75.4 tok/s | 92 ms | **4.66 s** |
| vLLM · 27B 无审查 + DFlash2 | **93.7 tok/s** | 133 ms | 5.08 s |
| vLLM · 27B 无审查 + 自带 MTP | 69.9 tok/s | 141 ms | 5.17 s |

- vLLM 的草稿头：DFlash2（7 tokens，接受 ~3.46/窗口）比自带 MTP（4 tokens，~2.98/窗口）**decode 快约 25%**。
- 方法学：vLLM 会把约 2.8 个 token 合并进一个 SSE chunk，按 chunk 计数会低估 decode，已改用服务端 `completion_tokens` 校正。

### 2.4 NVLink 到底有没有用

| 场景 | decode | 6K 提示读取 |
|---|---:|---:|
| vLLM TP=2，NVLink 开 | 75.4 tok/s | 4.66 s |
| vLLM TP=2，NVLink 关 | 74.3 tok/s | 6.32 s |
| 收益 | **+1.5%** | **+35.6%** |

- 结论：在这台机上，NVLink 主要提速**读提示**，几乎不影响**生成**（生成受显存带宽限制）。
- **Strata 不经过 NVLink**：layer split 无 TP/AllReduce，验证窗口只传几百 KB 激活（PCIe ~6 GB/s 足够）。
- 因此"有 NVLink"不是选 Strata 或 vLLM 的决定因素。

### 2.5 质量

- 6 道题（数学陷阱、鸡兔同笼、LIS、two_sum、严格指令、中文 MoE 解释）：Strata 与 vLLM **全部通过、正确性打平**（代码题单元测试全绿）。
- 风格差异：Strata 更简洁；vLLM 更啰嗦、爱补充"常见错误答案"。
- 该套题偏中等难度，不能区分 125B 与 27B 的能力上限。

---

## 3. ⚠️ 已验证但**未上线**的优化：`--pipeline-windows 2`

- 生产服务读取的是 `strata-iq2_xs.json` / `strata-orca-iq3_xxs.json`，**都不含** `--pipeline-windows`。
- 带该参数的只有 `strata-iq2_xs.pw2.json` / `strata-orca-iq3_xxs.pw2.json` 两个变体，且这两个变体**早于** `reasoning_effort: none`，直接拿来用会把 no-think 配置丢掉。
- 若决定上线（+3.9% decode，代价 272 MiB/卡缓存、极小输出差异）：
  1. 在当前生产配置的 `args` 末尾追加 `"--pipeline-windows", "2"`；
  2. 保留 `"reasoning_effort": "none"`；
  3. 重启服务，日志应出现：
     `--pipeline-windows 2: N MiB of CUDA0 kept out of the expert cache ...`
- 若重视输出完全可复现 → 保持默认关闭。

---

## 4. 已否决 / 无收益的开关

| 开关 | 结果 | 说明 |
|---|---|---|
| `pipeline_windows_2`（首次测量） | −10.8% | **测量噪声**，已被 §2.2 推翻 |
| `--kv k8v4` | −3% | 量化收益不足 |
| `--prefill-help` | ±0% | 无收益 |
| `--pf-fused` | ±0% | 无收益 |
| `--layer-split 20` | ±0% | 与 auto(K=16) 等价 |

> 结论：decode 已接近本机上限（2080 Ti 算力 + PCIe 3.0 x8）。想再快只能换更小量化（如 Q2_0，约 +10%，质量略降）。

---

## 5. 已知问题与后续建议

1. **128K 上下文的显存余量告警**
   - 日志：`only 483 MiB of VRAM free at the start of this request (below 512 MiB)`，提示可能触发驱动换页、decode 掉到个位数。
   - 建议：`--vram-reserve-mib 768`，或下调 `--max-context` / `--batch`。
2. **上线 `--pipeline-windows 2`**（§3），预计 +3.9% decode。
3. **Orca 的 decode 波动较大**（64.5–79.0 tok/s），其 +3.9% 结论为"同向但不够确凿"；如需定论应增加重复次数。
4. **`STRATA_ROUTE_TAIL_SKIP=7` 默认开启**：在会 miss 专家的 12–16 GB 卡上 +10–20% decode，但输出与 0.1.41 有极小差异；需要完全一致时设 `0`。
5. **安全**：服务监听 `0.0.0.0:8080` 且使用 API key。本复盘与仓库中的配置样本**已移除真实 key**；建议把线上 key 换成独立随机长串，不要复用系统密码。

---

## 6. 复现与证据

```bash
# 速度基准（服务运行时；Strata:8080 需 key）
python3 /srv/share/strata-ops/strata-bench.py <标签> 3
python3 /srv/share/strata-ops/llm-bench.py <标签> http://127.0.0.1:8080 strata "$(cat /srv/share/strata-ops/strata-api-key.txt)" 3

# pipeline A/B
python3 /srv/share/strata-ops/pipeline-ab.py
/srv/share/strata-ops/pipeline-driver.sh          # IQ2_XS
/srv/share/strata-ops/pipeline-driver-orca.sh     # Orca

# 质量对比
python3 /srv/share/strata-ops/quality-bench.py
```

原始证据（本机）：
- 文档：`/srv/share/strata-ops/{DEPLOY-NOTES,BENCHMARK-vs-vLLM,PIPELINE-VALIDATION,QUALITY-vs-vLLM}.zh-CN.md`
- 日志：`/srv/share/strata-ops/logs/`（`pipeline-*`, `bench*`, `strata-calibrate.log`）
- 结果：`/srv/share/strata-ops/results/`
- 配置备份：`/srv/share/strata-ops/backups/`
- 本仓库 `configs/` 为**脱敏后**的生产配置样本（`api_key` 已替换为 `<REDACTED>`）。

---

## 7. 局限

- 单机、单用户、单请求基准；并发/批处理未覆盖。
- decode 受温度/功耗/缓存命中影响，单次波动可达 ±10%（Orca 尤甚）。
- 调优前后对比（§2.1）与 pipeline A/B（§2.2）不是同一批次，不能简单叠加为 +10%。
- 128K 上下文与 `reasoning_effort=none` 未做正式 A/B，仅记录为配置变更。
- 质量对比为 6 题小样本，不代表模型能力上限。

---

## 8. 原始档案（备份存档）

- [`archive/strata-ops/`](archive/strata-ops/)：原始部署文档、基准脚本、日志、结果与配置备份。
- [`archive/engine-logs/`](archive/engine-logs/)：Strata 引擎运行日志（IQ2_XS / Orca）。

> 归档时已排除 `.hf_token` 与 `strata-api-key.txt`，并把所有配置/文档中的真实 API key 脱敏为 `<REDACTED>`。详见 [`archive/README.md`](archive/README.md)。

---

## 9. 2026-10-23 更新：按 IQ3_S 双 2080Ti 指南优化 262K

> 对象：`SC117 Qwen3.8-Flash-Next abliterated IQ3_XXS`，262144 context，2×2080Ti 22G，本机约 60 GiB 可用内存，引擎 0.1.44.1。
> 约束：**不下载新权重、不重编译引擎**，只使用 0.1.44.1 已支持的开关。参考文档的 9 个 sm_75 PR 批次（v0.1.43）在本机二进制中大多没有对应 env（见 §9.5），因此未打补丁、也未设置无效变量。

### 9.1 最终改动（已生效）

配置文件：`/srv/share/Strata/strata-sc117-iq3_xxs.json`（样本见 [`configs/strata-sc117-iq3_xxs.json`](configs/strata-sc117-iq3_xxs.json)）

| 项 | 原值 | 新值 | 说明 |
|---|---|---|---|
| `layer_split` | `20` | **`24`** | 48 层在两张 22G 卡上对半；本机扫描 18/20/22/24/26，24 最优 |
| `env.STRATA_BF16_TC` | 未设 | **`1`** | sm_75 的 BF16 投影转 FP16 张量核；prefill 主收益 |
| `env.STRATA_SELECT_SIMT` | 未设 | **`1`** | 0.1.44.1 只接受 `1`（参考文档的 `2` 在本版本不存在） |
| `env.STRATA_PREFILL_HELP` | 未设 | **`1`** | 层切分空闲卡分担单块短 prompt；长 prompt 自动不生效 |
| `env.STRATA_SPLIT_MTP_BATCH` | `1` | `1` | 保留 |
| `--pipeline-windows` | 无 | **`2`** | NVIDIA 默认关，显式开；decode 窗口跨两 stage 重叠 |
| `--conversation-cache-*` | 无 | **`4096 / 8 / min-tokens 2048`** | 60 GiB 机器留余量；未照抄指南的 16384/12 |
| `--prefill` | `auto` | **`auto`（保持）** | `auto:16384` 在本机反而更慢，见 §9.4 |
| `--max-context` / `--kv` / `--kv-resident` | 262144 / int8 / 32768 | 不变 | 指南同款 |
| `--vram-reserve-mib` | `1024` | 不变 | 指南 700 偏激进；262K 下保留 1024 |
| vision | GPU | 不变 | 视觉实测正常；改 CPU 对文本速度无收益 |

备份：`/srv/share/strata-ops/backups/strata-sc117-iq3_xxs.json.pre-opt-20261023-142008`。
原始策略快照：[`docs/ORIGINAL-STRATEGY-sc117-262k.zh-CN.md`](docs/ORIGINAL-STRATEGY-sc117-262k.zh-CN.md)；原始配置样本：[`configs/strata-sc117-iq3_xxs.pre-opt.json`](configs/strata-sc117-iq3_xxs.pre-opt.json)。

### 9.2 实测（同机、262K、单请求、greedy、thinking off）

| Prompt | 基线 tok/s | 优化后 tok/s | 变化 |
|---|---:|---:|---:|
| 6.0K prefill | 901.0 | **1060.1** | **+17.7%** |
| 23.8K prefill | 1345.3 | **1752.2** | **+30.3%** |
| 89.2K prefill | 1467.3 | **2196.8** | **+49.7%** |
| decode（256 tok） | 74.3 | **84.1** | **+13%**（保守 +8–13%） |

- 基线：split 20、无 env 补丁、无 pipeline、8K chunk。
- 优化后：split 24、BF16_TC+SIMT+HELP、pipeline 2、8K chunk。
- decode 波动较大：基线 2 次（69.7 / 78.8），最终 5 次（81.6–87.0，中位 84.1）。prefill 多次重复误差约 1–2%。
- 原始输出：[`results/2026-10-23-iq3_xxs-262k/`](results/2026-10-23-iq3_xxs-262k/)。

### 9.3 分项归因

| 组合 | 6K | 23.8K | 89.2K | decode | 结论 |
|---|---:|---:|---:|---:|---|
| 基线（split20） | 901 | 1345 | 1467 | 74.3 | — |
| + env（BF16_TC/SIMT/HELP） | 1051 | 1632 | 1932 | 74.7 | prefill **+17/+21/+32%**，decode 不变 |
| + pipeline 2 | 1047 | 1625 | 1925 | 77.9 | decode **+4.2%**，prefill 持平 |
| + split 24 | 1065 | 1784 | 2238 | 83.5 | 相对 split20 再 **+2/+10/+16%**（prefill） |

层切分扫描（env+pipeline 固定，单位 tok/s）：

| split | 6K | 23.8K | 89.2K | decode |
|---:|---:|---:|---:|---:|
| 18 | 1028 | 1541 | 1767 | 75.1 |
| 20 | 1047 | 1625 | 1925 | 77.9 |
| 22 | 1059 | 1676 | 2023 | 81.2 |
| **24** | **1065** | **1784** | **2238** | **83.5** |
| 26 | 1064 | 1779 | 2236 | 82.8 |

### 9.4 没有照抄的项（本机实测否决）

- **`--prefill auto:16384`**：split24 下 6K 持平、23.8K **−21%**、89.2K **−3%**。16K chunk 要借走每卡约一半专家缓存（7.26 GiB），中等长度 prompt 的专家 miss 抵消了大 chunk 收益。保留 `auto`（8K）。
- **`--conversation-cache-mib 16384 --slots 12`**：262K 加载后 `MemAvailable` 只剩约 9 GiB，照抄会挤压引擎/系统；改为 4096/8，并加 `min-tokens 2048` 防短请求占槽。
- **vision 改 CPU**：文本路径专家命中率已接近 100%，腾出的显存换不到 decode 收益；GPU 视觉保留。
- **`reasoning_budget_tokens: 4000`**：服务默认仍是 `reasoning_effort: none`（短答/测速必须），思考由请求级覆盖。

### 9.5 参考文档与 0.1.44.1 的差异

参考文档基于 v0.1.43 + 9 个 sm_75 PR。本机 0.1.44.1 中**不存在**以下 env（设置也是空操作），因此没有写入：

`STRATA_PA_V2T`、`STRATA_REFILL_PARTS`、`STRATA_XN_F16`、`STRATA_TOPK_SAMPLE`、`STRATA_SM75_IL`、`STRATA_SM75_EXP`、`STRATA_GR_UP75`、`STRATA_SCORES_HALVE`、`STRATA_TOPK_SPLIT`、`STRATA_TC_SM75`。

`STRATA_SELECT_SIMT` 在本版本只判断 `"1"`，文档的 `2` 不会生效；`--pipeline-windows` 在 NVIDIA 上仍是 opt-in（AMD gfx12 才默认开）。

### 9.6 功能验收

- 短答 3/3：巴黎、5、疑是地上霜。
- 针召回 **12/12**：1k/32k/64k/128k × 深度 10/50/90（`tools/needle_bench.py`，thinking off）。
- 视觉 1/1：生成含 `7349` 的 PNG，data URL 发送，模型答 `7349`。
- 262K 启动正常，两卡空闲显存约 885 / 795 MiB（含 pipeline 预留）。

### 9.7 顺带同步到其他配置

`strata-iq2_xs.json`、`strata-orca-iq3_xxs.json` 也加入了同一组 env、`--pipeline-windows 2`、conversation cache（未改 `layer_split: auto`）。IQ2_XS 复测：6K prefill **1071 tok/s**（旧值 910，+17.7%），decode 85.6 tok/s（与旧值 87.8 同量级）；Orca 未复测。

> 262K 仍是风险档：若启动期/长读出现 arena 或显存不足，先回退 `--max-context 204800` 与 `layer_split 22`，其余开关可保留。
