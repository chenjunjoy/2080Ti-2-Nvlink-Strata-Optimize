# Strata vs vLLM 速度对比(本机 2×RTX 2080 Ti + NVLink)

日期:2026-10-17(更新)· 方法:同一台机、同两张卡、greedy、关闭思考、逐次唯一提示(避开缓存)、各 3 次取中位数。
**三者互斥**:Strata / vLLM 各自独占两张卡。ComfyUI 亦占用显存,测试期间已停。

## 服务与模型

| | Strata IQ2_XS | Strata Orca(无审查) | vLLM |
|---|---|---|---|
| 模型 | Qwen3.8-Flash-Next IQ2_XS(125B MoE) | OrcaRouter Uncensored IQ3_XXS(125B MoE,微调) | Qwen3.8-27B-NVFP4(27B) |
| 上下文 | 131072 | 32768 | 262144 |
| 并行方式 | 层并行(无 TP) | 层并行(无 TP) | **张量并行 TP=2** |
| 端口/鉴权 | 8080 / 需 key | 8080 / 需 key | 8000 / 无 |

> 另有 vLLM 的**无审查服务** `vllm-uncensored`(systemd,端口 **8002**),模型 `Qwen3.8-27B-Uncensored` = **Qwen3.8-27B-abliterated-NVFP4**(27B,去审查微调),TP=2、256K 上下文。与 `vllm.service`、Strata 互斥(均独占两卡)。

## 结果(单请求,decode 用服务端 token 数校正)

| 服务 · 模型 | decode | TTFT | 6K 提示读取 |
|---|---:|---:|---:|
| **Strata · IQ2_XS** | **84.3 tok/s** | 78 ms | 6.61 s |
| Strata · Orca IQ3_XXS | 69.6 tok/s | 86 ms | 6.72 s |
| **vLLM · 27B NVLink 开** | 75.4 tok/s | 92 ms | **4.66 s** |
| vLLM · 27B NVLink 关 | 74.3 tok/s | 94 ms | 6.32 s |
| vLLM · 27B Uncensored(abliterated)**DFlash2** 草稿 ← 当前(长期) | **93.7 tok/s** | 133 ms | 5.08 s |
| vLLM · 27B Uncensored(abliterated)自带 MTP 草稿 | 69.9 tok/s | 141 ms | 5.17 s |

## NVLink 的实际收益(vLLM TP=2,同模型对比)

| 指标 | NVLink 开 | NVLink 关 | 收益 |
|---|---:|---:|---:|
| decode | 75.4 tok/s | 74.3 tok/s | **+1.5%** |
| 6K 提示读取 | 4.66 s | 6.32 s | **+35.6%** |

**结论:NVLink 主要提速"读提示",几乎不影响"生成"。** 生成是显存带宽瓶颈,不是卡间通信。

> NVLink 硬件:`GPU0↔GPU1 = NV2`,2×25.781 GB/s(≈51.6 GB/s),P2P OK。
> **Strata 用不到 NVLink**:层并行只在每个验证窗口传一次 token 激活(走 PCIe,~6 GB/s,数据量仅几百 KB),无 TP、无 P2P。

## 无审查版 Orca 调优记录

初测 6K 提示读取 **21.6 s**,原因是按官方 `docs/ORCA.md` 用了 `--prefill 512`(小分块)。
改为 **`--prefill auto`** 后 → **6.72 s(快 3.2×)**,与 IQ2_XS 持平。配置:`strata-orca-iq3_xxs.json`。

## abliterated vLLM 的草稿头(投机解码)更换记录

同一模型、同一方法,只换草稿头:

| 草稿头 | 每次推测 token | decode | 6K 提示 | 每次窗口接受 |
|---|---:|---:|---:|---:|
| **DFlash2**(外部草稿模型) | 7 | **93.2 tok/s** | 5.11 s | ~3.46 token |
| **模型自带 MTP**(`method=mtp`)← 当前 | 4 | 69.9 tok/s | 5.17 s | ~2.98 token |

**结论:换成本模型自带 MTP 头后,decode 慢约 25%,prefill 不变。**
原因是 DFlash2 的草稿**接受率更高**(3.46 vs 2.98 token/窗口)。若追求生成速度,DFlash2 更优;
自带 MTP 的好处是**无需额外草稿模型**、更自洽。

> **决定:长期保持 DFlash2。** 已把 `vllm-uncensored-run.sh` 恢复为 `method=dflash`(7 tokens,草稿 `/srv/share/models/Qwen3.8-27B-DFlash2`)并重启生效,复测 decode **93.7 tok/s**。

## 结论 / 选型

- **生成最快 + 模型最强** → **Strata IQ2_XS**(84 tok/s,125B,中文好)。
- **读长提示最快 / 256K 上下文 / 吃 NVLink** → **vLLM 27B**(6K 提示 4.66 s)。
- **要无审查**:
  - **vLLM 27B abliterated**(`vllm-uncensored`:8002)→ **生成最快(93.2 tok/s)**,256K 上下文;27B 规模。
  - **Strata Orca IQ3_XXS**(125B)→ 模型大得多,32K 上下文,生成 69.6 tok/s。
- ⚠️ **注意**:两个"无审查"是**不同模型**——`Qwen3.8-27B-abliterated`(27B)vs `OrcaRouter Uncensored`(125B),不通用。
- NVLink 不构成"必须用 vLLM"的理由 —— 它只让 vLLM 的**读提示**快约 35%,生成仅 +1.5%。

## 方法学注意

- vLLM 会把约 **2.8 个 token 合并进一个 SSE chunk**,按 chunk 计数会**低估** decode(原始的 ~26.5 实为 ~75)。本表已改用服务端 `completion_tokens` 校正。
- 测 prefill 时每个提示加了唯一前缀,避免命中 prefix cache 造成假快。
- 原始日志:`logs/bench*.txt`、`logs/bench2-*.txt`。

## 复现

```bash
# 服务在运行时(Strata:8080 需 key;vLLM:8000 无需 key)
python3 /srv/share/strata-ops/llm-bench.py <标签> http://127.0.0.1:8080 strata "$(cat /srv/share/strata-ops/strata-api-key.txt)" 3
python3 /srv/share/strata-ops/llm-bench.py <标签> http://127.0.0.1:8000 Qwen3.8-27B-NVFP4 - 3 '{"chat_template_kwargs":{"enable_thinking":false}}'
# NVLink 关的对照:vLLM 启动前设 VLLM_DISABLE_CUSTOM_ALL_REDUCE=1 NCCL_P2P_DISABLE=1
```
