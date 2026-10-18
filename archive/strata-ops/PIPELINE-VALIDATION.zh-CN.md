# Strata `--pipeline-windows` 验证报告

> 目的:核实"除了 layer split 还要不要 pipeline"这一说法,并用官方文档 + 本机实测给出结论。
> 生成于 2026-10-17(已完成,两阶段实测 + 官方引用)。

---

## 一、官方说明(写在最前)

**出处:`docs/MULTI_GPU.md` → 章节 `One conversation with both cards busy (--pipeline-windows, ...)`**
(GitHub:`https://github.com/Niko1221/Strata/blob/main/docs/MULTI_GPU.md`)

### 1. 默认值与开关
> **Default on AMD RDNA4 (gfx1200 / gfx1201).** With `--serve`, the draft layer and a layer split of **two or more stages**, `--pipeline-windows 2` is on unless you say otherwise (the log says "is on by default for a layer split of N stages"; two stages since 0.1.44, three or more since 0.1.43). It is no quality trade: the tokens are the serial loop's up to CPU rounding. `--pipeline-windows 0` or `STRATA_PIPELINE_AUTO=0` turns it off; `--pipeline-windows 2` asks for it on any split. ... **NVIDIA builds keep it opt-in.**

- `--pipeline-windows 2` → 开启(第一张卡先跑下一个窗口,与最后一张卡的验证重叠)
- `--pipeline-windows 1` → 只重叠短的提示读取
- `--pipeline-windows 0`(或 `STRATA_PIPELINE_AUTO=0`)→ 关闭
- **AMD RDNA4 默认开;NVIDIA 默认关(需手动加)**

### 2. 它做什么
> `--pipeline-windows 2` lets the first card start the **next** window while the last card still verifies this one. The next window is a guess... When the guess holds, half of the next window is already done; when it does not, the first card puts its state back... A guessed window is only started when the draft layer's estimate says it is likely to be kept.

### 3. 质量
> **It is no quality trade: the tokens are the serial loop's** up to CPU rounding.

### 4. 代价
> **Cost**: a second verify window on each card, **160 MiB more kept out of each card's expert cache**, plus two copies of the first card's recurrent state (about 3 MiB per GDN layer).

### 5. 何时会被自动关闭
> **Off** ... with `--batch` slots, `--peer-device`, the helper caches (`--expert-cache-device1..3`), a split onto one GPU, or **no draft layer**; on three or more stages also `--pipeline-windows 1` and `--adapt-async 1`.

### 6. 官方实测(2×RTX 3090,NVIDIA)
| Arm | Decode tok/s | Prefill tok/s |
|---|---:|---:|
| setup defaults | 137.0 | 1798 |
| **`--pipeline-windows 2`** | 136.7(≈持平)| **2097(+16.6%)** |
| pw2 + 其它优化 | 135.9 | 2296(+28%) |

其它官方数据点:
- Swift IQ3_XXS(4060Ti+5080,resident 模式):**decode 平均 +16%**(72.4 → 84.0);但"experts read through the OS file cache(`--mmap-experts`)时**测不出更快**"。
- 4×RX 7900 XT:decode +14%(59.4→67.6 @4K)。
- `docs/QUANTS.md`:3–4 卡时 `--pipeline-windows 0` 反而**帮助短回答(x1.3)**、**拖慢代码 6–20%**。

### 7. 怎么确认生效(引擎日志)
```
strata generate: --pipeline-windows 2: N MiB of CUDA0 kept out of the expert cache ...
strata serve:    --pipeline-windows 2: two verifiers per stage, 2 stages overlap across windows
```
关闭时打印 `... is off: <原因>`。

### 8. 官方立场小结
pipeline **不是 layer split 的必需项**,而是**独立的可选优化**:AMD 上默认开、主要提速读提示;NVIDIA 上默认关、且只在"窗口受 GPU 限制"时才见效。

---

## 二、本机验证

**方法:** 同一模型、同两张卡(2×2080 Ti + NVLink),只改 `--pipeline-windows`;
greedy、`reasoning_effort=none`、逐次**唯一提示**(避开缓存),每项取中位数。
- decode:256 token;prefill 6K 与 16K 提示各测。
- 环境:期间停掉 vLLM 与 open-webui,Strata 独占 8080。

### 阶段① Strata IQ2_XS(125B,128K)
| 指标 | 基准(无 pipeline) | `--pipeline-windows 2` | 变化 |
|---|---:|---:|---:|
| **decode** | 84.80 tok/s | **88.10 tok/s** | **+3.9%** |
| prefill 6K | 912.7 tok/s | 903.4 tok/s | −1.0% |
| prefill 16K | 1269.1 tok/s | 1265.7 tok/s | −0.3% |

### 阶段② Strata Orca 无审查 IQ3_XXS(125B,32K)
| 指标 | 基准(无 pipeline) | `--pipeline-windows 2` | 变化 |
|---|---:|---:|---:|
| **decode** | 71.60 tok/s | **74.40 tok/s** | **+3.9%** |
| prefill 6K | 884.3 tok/s | 888.3 tok/s | +0.5% |
| prefill 16K | 1180.7 tok/s | 1177.8 tok/s | −0.2% |

> Orca 的 decode 单次波动较大(基准 64.5/74.6/71.6,pw2 79.0/74.4/72.3),两组区间有重叠,所以 +3.9% 只是"同向"、不如 IQ2_XS 确凿。

---

## 三、结论

**① 对"除了 layer split 还要 pipeline"这个说法的判断:**
pipeline **不是必需项**,是**独立的可选优化**。官方在 AMD RDNA4 上默认开,在 **NVIDIA 上默认关**。

**② 本机实测(2×2080 Ti + NVLink,PCIe 3.0 x8):**
| | decode | prefill 6K | prefill 16K |
|---|---:|---:|---:|
| IQ2_XS | **+3.9%** | −1.0% | −0.3% |
| Orca 无审查 | **+3.9%** | +0.5% | −0.2% |

- **两个模型都得到约 +4% 的 decode 提升**,方向一致;
- **prefill 基本不变**(±1% 内);
- **与官方 2×3090 的结论方向相反**:官方是 prefill +16.6%、decode 持平。

**③ 为什么本机与官方不同:**
官方明说"pipeline **只在窗口受 GPU 限制时见效**;若专家从文件缓存读(`--mmap-experts`),测不出更快"。两台机的瓶颈位置不同(3090 更快、链路/缓存命中不同),所以收益落在不同环节:官方落在 prefill,本机落在 decode。

**④ 数据可信度:**
- IQ2_XS **干净**(两组区间不重叠:基准 84.8–85.1 vs pw2 86.3–88.2),+3.9% 可信;
- Orca **波动较大**,区间重叠,+3.9% 仅供参考(同向)。

**⑤ 代价:**
- 每卡少 **272 MiB** 专家缓存(本机日志实测;官方称 160 MiB/卡);
- 输出可能有极小取整差异(near-tie 可能翻转),但**质量不变**(官方:no quality trade)。

**⑥ 建议:**
- **要开就开**:在你这台机器上是**小而真实的 decode 收益(~+4%)**,prefill 不受影响;可接受微小输出差异的话值得开。
- 若你重视输出可复现性 → 保持默认(关)。
- ⚠️ **更正**:更早一次 A/B 得到的"decode −10.8%"是**测量噪声**(脚本/单次取样问题),已被本次严谨 A/B 推翻 —— 那次结论作废。

**⑦ 开启方式(官方写法):**
```json
"args": [ ..., "--pipeline-windows", "2" ],
"layer_split": "auto"
```

---

## 四、原始数据

- 阶段①:`logs/pipeline-baseline.txt`、`logs/pipeline-pw2.txt`
- 阶段②:`logs/pipeline-orca-baseline.txt`、`logs/pipeline-orca-pw2.txt`
- 驱动脚本:`pipeline-driver.sh`(IQ2_XS)、`pipeline-driver-orca.sh`(Orca)
- 基准脚本:`pipeline-ab.py`
