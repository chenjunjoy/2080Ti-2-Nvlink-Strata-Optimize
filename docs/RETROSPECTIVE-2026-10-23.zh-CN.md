# 复盘：按 IQ3_S 指南重调 Strata 262K（2026-10-23）

> 对象：SC117 Qwen3.8-Flash-Next abliterated IQ3_XXS，262144 context，2×RTX 2080Ti 22G，引擎 0.1.44.1。
> 约束：不下载新权重、不重编译引擎。
> 主文档：[`../README.md`](../README.md) §2.6 / §9；原始策略：[`ORIGINAL-STRATEGY-sc117-262k.zh-CN.md`](ORIGINAL-STRATEGY-sc117-262k.zh-CN.md)。

---

## 1. 结论

1. **prefill 提升是硬收益**：6K / 23.8K / 89.2K 分别 **+17.7% / +30.3% / +49.7%**，重复测量误差约 1–2%。
2. **decode 提升方向明确、幅度不够硬**：短测 74.3 → 84.1 tok/s（+13%），但基线只有 2 次、波动 ±10%；保守记 **+8–13%**。
3. **真实长文表现更好**：18,228 → 9,924 tokens，生成 **102.5 tok/s**，端到端 90.2 tok/s，MTP 接受 89.8%。
4. **主要收益来自三处**：`STRATA_BF16_TC=1`（prefill）、`layer_split 24`（prefill 长端 + decode）、`--pipeline-windows 2`（decode）。
5. **不能宣称全面超过 vLLM**：长文 decode 高于 vLLM 27B 的历史最好值 93.7，但短 decode 和 6K prefill 仍低于 vLLM；模型、量化、上下文、输出长度都不同。

---

## 2. 变更与时间线

| 时间 | 动作 | 结果 |
|---|---|---|
| 14:20 | 建立基线（split 20、无 env、无 pipeline、8K chunk） | 6K 901、24K 1345、89K 1467、decode 74.3 |
| 14:20 | 加 `BF16_TC + SELECT_SIMT + PREFILL_HELP` | prefill 1051 / 1632 / 1932，decode 74.7 |
| 14:22 | 加 `--pipeline-windows 2` | decode 77.9（+4.2%），prefill 持平 |
| 14:24 | 层切分扫描 18 / 20 / 22 / 24 / 26 | 24 最优：1065 / 1784 / 2238、decode 83.5 |
| 14:27 | 试 `--prefill auto:16384` | 24K **−21%**、89K −3%，否决 |
| 14:31 | 写入生产配置并重启 | 最终受控值 1060 / 1752 / 2197、decode 84.1（5 次中位） |
| 15:57 | 用户真实长文请求 | 18,228 → 9,924，prefill 1378.5、decode 102.5 |

最终配置：`/srv/share/Strata/strata-sc117-iq3_xxs.json`
备份：`/srv/share/strata-ops/backups/strata-sc117-iq3_xxs.json.pre-opt-20261023-142008`

---

## 3. 数据

### 3.1 受控 A/B

| 组合 | 6K | 23.8K | 89.2K | decode |
|---|---:|---:|---:|---:|
| 基线 split20 | 901 | 1345 | 1467 | 74.3 |
| + env | 1051 | 1632 | 1932 | 74.7 |
| + pipeline 2 | 1047 | 1625 | 1925 | 77.9 |
| + split 24 | 1065 | 1784 | 2238 | 83.5 |
| 最终复测（中位） | 1060 | 1752 | 2197 | 84.1 |

### 3.2 层切分扫描

| split | 6K | 23.8K | 89.2K | decode |
|---:|---:|---:|---:|---:|
| 18 | 1028 | 1541 | 1767 | 75.1 |
| 20 | 1047 | 1625 | 1925 | 77.9 |
| 22 | 1059 | 1676 | 2023 | 81.2 |
| **24** | **1065** | **1784** | **2238** | **83.5** |
| 26 | 1064 | 1779 | 2236 | 82.8 |

### 3.3 真实长文请求（非受控）

| 指标 | 数值 |
|---|---:|
| prompt | 18,228 tokens，13,223 ms → 1,378.5 tok/s |
| 生成 | 9,924 tokens，96,784 ms → 102.5 tok/s |
| 端到端 | 110 s → 90.2 tok/s |
| MTP 接受 | 6,774 / 7,544 = 89.8% |
| suffix drafts | 1,251 / 1,286 |
| 专家缓存 | 100.0%（0.6% 经 PCIe） |
| KV 常驻 | 99.89%（170 MiB 从 RAM） |

---

## 4. 归因与可信度

| 结论 | 可信度 | 说明 |
|---|---|---|
| BF16_TC 等 env 提升 prefill | **高** | 同机同模型，6K/24K/89K 同向，幅度 17–32% |
| split 24 优于 20 | **高（prefill）/ 中（decode）** | prefill 稳定；decode 单次波动大，22/24/26 差距接近噪声 |
| pipeline 2 提升 decode | **中高** | 与 2026-10-17 的 +3.9% 同向；本次 +4.2% |
| decode +13% | **中** | 基线仅 2 次；建议按 +8–13% 记账 |
| 16K chunk 有害 | **中高** | 两个 split 下 24K 都掉约 20%，不是单点异常 |
| 真实长文 102.5 tok/s | **高（事实）/ 低（外推）** | 长输出 + 高 suffix 接受率，换成短答会低很多 |
| 全面快于 vLLM | **不成立** | 口径不同；短 decode / 6K prefill 仍 vLLM 快 |

### 关键原因

- `STRATA_BF16_TC=1` 把 sm_75 的 BF16 投影转到 FP16 张量核，直接加速 prefill。
- `layer_split 24` 让 48 层在两张 22G 卡上接近对半，减少单卡层数/专家压力；长 prompt 收益最大。
- `--pipeline-windows 2` 让两张卡的 verify 窗口重叠，主要改善 decode；代价是每卡约 272 MiB 专家缓存。
- 16K chunk 要借走每卡约一半专家缓存（7.26 GiB），22G 卡上中等长度 prompt 反而变慢。

---

## 5. 与 vLLM 的比较边界

| 场景 | Strata 现在 | vLLM 最好 | 结论 |
|---|---:|---:|---|
| 长文 decode（9.9K out） | 102.5 | 93.7（27B DFlash2，256 out） | Strata 高约 9%，但输出长度不同 |
| 短 decode（256 out） | 84.1 | 93.7 | vLLM 快约 11% |
| 6K prefill | 1,060 | 约 1,180–1,280 | vLLM 快约 10–20% |
| 128K prefill | 2,163 | 未测 | 只有 Strata 有 262K 数据 |

- 模型不同：Strata 125B MoE IQ3_XXS vs vLLM 27B NVFP4。
- 输出长度不同：长文进入稳态，均速天然高于 256-token 短测。
- 任务形状不同：本次 suffix drafts 接受了 97.3%，对 decode 有明显抬高。
- 严格结论必须同 prompt、同输出长度、同温度做 A/B；目前只能按场景说。

---

## 6. 失误与修正

1. **改错参数**：用字符串替换第一个 `auto`，把 `--expert-cache auto` 改成了 `auto:16384`，`--prefill` 没变。日志显示 `prompt chunk auto: 8192` 才发现。
   - 修正：按 flag 名定位参数值，不按值替换。
2. **进程管理混乱**：`pkill -f` 匹配到执行命令的 shell 自身；`$!` 记录的是子 shell 而非 Python PID；服务有时不响应 SIGTERM，旧引擎继续占显存，导致新服务 `port already in use`。
   - 修正：写 `/tmp/opencode/stop-strata.py`，按 `/proc` 找 server 并递归杀子进程；每次启动前核对端口、PID、显存。
   - 遗留问题：sc117 仍靠手工启动，没有 systemd 单元。
3. **decode 基线重复次数不足**：基线 2 次、最终 5 次，+13% 的置信度有限。
   - 教训：以后 decode A/B 至少 5 次对 5 次，报告区间而不是单点。
4. **层切分每个 K 只跑一轮**：prefill 稳定，但 decode 不足以区分 22/24/26。
   - 结论仍取 24，但“最优”应理解为“最好一档”，不是统计显著。
5. **把 IQ2_XS / Orca 一并改掉**：IQ2_XS 只复测了 6K/24K，Orca 未复测。
   - 风险：Orca 的 decode 本来波动大，pipeline 收益可能被噪声掩盖；需要时单独回测。
6. **差点照抄 16384/12 会话缓存**：262K 加载后只剩约 9 GiB 可用内存，照抄会挤压引擎。
   - 修正：4096/8 + min-tokens 2048；针测中实际停车成功，未 OOM。
7. **“最快”表述过早**：真实长文 102.5 是特定任务，不等于短答/短提示也最快。
   - 修正：文档与结论都改为分场景表述。

---

## 7. 风险

- **262K 仍是风险档**：启动期 arena 或长读可能耗尽内存/显存；备 `--max-context 204800` 回退。
- **显存余量偏紧**：加载后 885 / 795 MiB；请求中 verify 窗口会降到约 649 MiB。低于 512 MiB 时驱动可能换页，decode 会塌。
- **会话缓存耗 RAM**：本次真实请求停车约 3 GB；多会话并行时要观察 `MemAvailable`。
- **手工进程**：重启/退出不会自动恢复；建议补 systemd 单元，或至少用脚本管理 PID。
- **Orca/IQ2 未完整复测**：参数已改，性能结论只对 SC117 成立。

---

## 8. 下一步

1. **同口径 vLLM A/B**（可选）：同一 18K prompt、9,924 输出、temperature 0，比较 Strata 与 vLLM 27B DFlash2。
2. **decode 统计加强**：每个配置 5 次，报告均值/中位/区间；把 22/24/26 再各跑 3 次。
3. **262K 稳定性**：连续 3 次 200K+ 读，观察显存余量与是否触发 <512 MiB 告警；必要时把 reserve 提到 1152。
4. **Orca 复测**：确认 env + pipeline 对 Orca 不是负收益。
5. **systemd 化**：为 `strata-sc117` 建 unit，和 IQ2/Orca/vLLM 互斥；把 stop/start 从 pkill 改为 `systemctl`。
6. **多轮会话缓存验证**：两个会话交替，确认 4096/8 的命中率与内存占用。
7. **补齐回退档**：准备 `204800` 配置并实际启动一次，避免真出问题时才试。

---

## 9. 证据索引

- 受控基准：`results/2026-10-23-iq3_xxs-262k/bench-*.txt`
- 真实长文：`results/2026-10-23-iq3_xxs-262k/user-longform-1557.txt`
- 针召回：`results/2026-10-23-iq3_xxs-262k/needle-final.txt`
- 引擎日志：`/srv/share/Strata/strata-sc117-iq3_xxs.log`
- 原始策略：`docs/ORIGINAL-STRATEGY-sc117-262k.zh-CN.md`
- 参考指南原文：`reference/Qwen3.8-Flash-Next-IQ3_S-dual-2080Ti-262K-deploy-guide.zh-CN.md`
