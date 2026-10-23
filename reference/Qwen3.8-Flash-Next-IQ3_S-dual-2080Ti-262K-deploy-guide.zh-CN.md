> **存档说明**：以下为参考文档原文，2026-10-23 按用户要求原样保存（仅去掉聊天外层引用）。
> 来源：用户提供的《Strata 部署指南：Qwen3.8-Flash-Next（IQ3_S）· 双 RTX 2080Ti 22G》，文档版本 2026-10-12。
> 本机实际采用/未采用项见 [`../README.md`](../README.md) §9 与 [`../docs/ORIGINAL-STRATEGY-sc117-262k.zh-CN.md`](../docs/ORIGINAL-STRATEGY-sc117-262k.zh-CN.md)。

---

# Strata 部署指南：Qwen3.8-Flash-Next（IQ3_S）· 双 RTX 2080Ti 22G

> 参考实现：Linux + 双卡层切分（layer split）+ 262144 上下文 + MTP 投机解码 + 视觉（CPU 编码器）。
>
> 文中路径用 `/path/to` 占位；性能数字为参考机实测（2× RTX 2080Ti 22G、92 GB DDR5、NVMe、CUDA 13.0）。
>
> 文档版本：2026-10-12 · 引擎基线 v0.1.43 + sm_75 批次补丁。

## 0. 一页速览

- **权重**：`ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF`（量化档 `IQ3_S`，GGUF 双分片）。
- **引擎**：Strata v0.1.43（上游 tag）+ sm_75 批次补丁（9 个未合入上游的 PR，见 §3.1；cherry-pick 单提交，勿 merge）。
- **必需 env**：`STRATA_BF16_TC=1`（Turing FP16 张量核预填充）、`STRATA_SELECT_SIMT=2`（QSA FP32 评分器 SIMT 档）、`STRATA_PA_V2T=1`（int8 prompt attention v2）、`STRATA_REFILL_PARTS=1`（借槽回收走 GGUF pieces）、`STRATA_PREFILL_HELP=1`（层切分空闲卡分担短 prompt 专家流）。
- **关键参数**：`--layer-split 26` · `--prefill auto:16384` · `--spec 4 --spec-min-p 0.70` · `--pipeline-windows 2` · `--max-context 262144` · `--kv int8 --kv-resident 32768` · `--conversation-cache-mib 16384 --conversation-cache-slots 12` · `--expert-cache auto` · `--vram-reserve-mib 700` · `--vision`。
- **思考默认**：配置 `reasoning_budget_tokens: 4000`；请求级 `reasoning_effort: medium`。

## 1. 硬件与软件前提

- **GPU**：2× RTX 2080Ti 22G（Turing，sm_75）；引擎需 ≥ v0.1.43 并含 sm75 内核（本地编译即可）。
- **内存**：全部专家常驻 RAM ≈ 62 GB 级（92 GB 机器留余量）；n-gram 表（~29 GB）与权重落 NVMe → 建议可用空间 ≥ 120 GB（分片 83.6 GB + pack/表/MTP）。
- **软件**：Debian/Ubuntu 系 Linux；CUDA 13.0；驱动 615+；构建链 gcc-15（系统默认 gcc 16 会被 nvcc 拒绝）；Python 3.13。
- **下载渠道**：83.6 GB 权重优先国内渠道（ModelScope 镜像实测 ~69 MB/s；hf-mirror 单流 ~1.5–5 MB/s）。

## 2. 权重获取与校验

来源：HF 仓库 `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF` 的 `IQ3_S` 子目录。

| 文件 | 大小（B） | SHA256 |
|---|---:|---|
| `Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf` | 54,817,524,224 | `4c1eb2ceb4915e1192f4f386021897bde56a97f40a0bb78bb86465e0f7d2aca3` |
| `Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf` | 28,800,138,432 | `316b46f3a2dbd68c900f43136ab9449f9dcc3725dfd8c794847c204bc161e113` |
| `mmproj-Qwen3.8-Flash-Next-BF16.gguf`（视觉可选） | 907,543,008 | `b1a82259702816a5330d7bd7607cd9676b11780e79ff7348c21103ff3ce49bd0` |

MTP 草稿层（~4.9 GB，31 张量）：由 setup 附带的 `tools/mtp_fetch.py` 获取（幂等可续跑）；其仓库常量默认 huggingface，改成国内镜像可提速。

## 3. 安装

```bash
git clone --depth 1 https://github.com/Niko1221/Strata.git /path/to/strata
cd /path/to/strata
uv venv --seed --python python3.13 .venv  # uv 建 venv 可绕开缺 ensurepip 的系统
./.venv/bin/python setup.py --family qwen --model IQ3_S \
    --gguf-dir /path/to/IQ3_S --data-dir /path/to/Strata-data \
    --context 262144 --vision cpu --yes --no-start
```

- `--gguf-dir` 指向自备分片目录（跳过官方下载，但会读 GGUF 头校验，截断分片在此报错停止）。
- 有 nvcc 时默认本地编译引擎（16 核约 2 分钟级）；产物 `engine/strata` + `engine/BUILD.json`。
- **构建硬规矩**：① 先停服务再编译；② 显式指定 `CC=/usr/bin/gcc-15 CXX=/usr/bin/g++-15 CUDAHOSTCXX=/usr/bin/g++-15`；③ 换版本/换编译器前先移走 `build/` 目录——旧 `CMakeCache.txt` 会无视 CC/CXX（混编后在链接期报 `std::__detail::__notify_impl/__wait_impl` 未定义）；④ 编完核对 `build/CMakeCache.txt` 的编译器路径与 `engine/BUILD.json`。
- setup 会重写服务配置（`host` / `api_key` / `layer_split` 可能被抹）→ 跑完核对并恢复存档配置。

### 3.1 sm_75 批次补丁（双 2080Ti 建议打上）

v0.1.43 基线上叠加 9 个上游 PR（作者在 RTX 2080 Ti 实测；多数默认生效、位级一致或仅选择序微差）：

| PR | 内容 | 生效方式 |
|---|---|---|
| #2071 | QSA 块评分 SIMT=2（prompt 长端加速） | `STRATA_SELECT_SIMT=2` |
| #2092 | int8 prompt attention v2（寄存器暂存） | `STRATA_PA_V2T=1` |
| #2091 | xn16→FP16（Turing FP16 张量核路径扩展） | 默认开（`STRATA_XN_F16=0` 关） |
| #2093 | prompt top-k 单读（>28K blocks 启用） | 默认开（`STRATA_TOPK_SAMPLE=0` 关） |
| #2069 | decode matvec Turing 表 + 专家布局模式4 | 默认开（`STRATA_SM75_IL=0` / `STRATA_SM75_EXP=0` 关） |
| #2070 | 超连接 decode 内核（窗口 ≥3 起效） | 默认开（`STRATA_GR_UP75=0` / `STRATA_GR_DOWN_TG=0` 关） |
| #2072 | decode QSA 长上下文单侧化 top-k | 默认开（`STRATA_SCORES_HALVE=0` / `STRATA_TOPK_SPLIT=0` 关） |
| #2081 | BF16 反量化 16B store | 默认开（`STRATA_TC_SM75=0` 关） |
| #2078 | 借槽回收走 GGUF mapping pieces | `STRATA_REFILL_PARTS=1` |

```bash
for N in 2072 2093 2071 2091 2092 2069 2070 2081 2078; do
    git fetch origin pull/$N/head:pr$N
done
# 浅克隆先加深历史，否则 git merge-base 报错（无共同祖先）
git fetch --deepen=600 origin
git checkout -b patch-sm75-1012 v0.1.43
# 逐 PR 只摘自己的提交（#2093 携带 #2072 的提交，先去重；顺序建议 2072→2093→其余）
for P in "v0.1.43 pr2072" "pr2072 pr2093" "v0.1.43 pr2071" "v0.1.43 pr2091" "v0.1.43 pr2092" \
         "v0.1.43 pr2069" "v0.1.43 pr2070" "v0.1.43 pr2081" "v0.1.43 pr2078"; do
    set -- $P
    git rev-list --reverse $(git merge-base $1 $2)..$2 | while read C; do
        git cherry-pick $C || { echo "冲突：$C"; break; }
    done
done
```

（本批次在参考机上 10 提交零冲突摘取；个别 PR 若与你的本地状态冲突，按「保留本地结构、把新块放语义等价位置」处理。）

## 4. 关键参数（逐项说明）

| 参数 | 值 | 说明 |
|---|---|---|
| `--layer-split` | `26` | 双卡层切分：第 2 张卡从第 26 层起（标量，写数组会启动失败）。同型双卡可扫描 K（本配置 26 优于 auto 23，约 +12%）。 |
| `--prefill` | `auto:16384`（上限 16384） | 预填充分块上限；实测 16384 为三点综合最优（8192 短赢长输，32768 长端更差）。 |
| `--spec` / `--spec-min-p` | `4` / `0.70` | MTP 投机：草稿 4；提议阈值 0.70（0.50 提议量 +30–50% 但接受率降，净速度零收益）。 |
| `--pipeline-windows` | `2` | 双卡 verify 窗口跨 stage 重叠（需恰好 2 stage + MTP + 无 `--batch` /helper）；实测一般任务 decode +8–13%、计数类 +36–58%、自由散文 ~+1%；代价：首卡专家缓存 −112 槽、启动 +~100s；条件不满足会打 `--pipeline-windows N is off: <原因>` 并静默回退。 |
| `--max-context` | `262144` | 上下文上限；KV int8 ≈ 15.3 KB/token（262K ≈ 4.0 GB）。风险档：上游同型机报告启动/分配阶段可能耗尽权重 arena（最坏冻结主机）→ 生产同时备 204800 回退档。 |
| `--kv` / `--kv-resident` | `int8` / `32768` | KV 量化 + 每 QSA 层 32768 cells 常驻显存（其余在 pinned RAM 按块上传，命中 ~99.7%）。 |
| `--expert-cache` | `auto` | 专家缓存自动求解（参考机 8872 专家/卡、16 GiB 级，解码命中 ~95%）。 |
| `--vram-reserve-mib` | `700` | 视觉/余量预留。 |
| `--conversation-cache-mib` / `--conversation-cache-slots` | `16384` / `12` | 会话前缀停车缓存；多轮前缀复用按 16384 块对齐（不足一块不复用）。 |
| `--vision`（`--vision cpu`） | 开 | 视觉编码器走 CPU（不占显存）；开启后 `/v1/models` 的 `input_modalities` 含 `image`。 |
| `--mtp` / `--pack` / `--native` / `--ple-gguf` / `--expert-profile` | — | 资源路径（setup 生成/写入配置）。 |
| 思考控制 | `reasoning_budget_tokens: 4000` | 请求级 `reasoning_effort: none\|low\|medium\|high`，或 `chat_template_kwargs.enable_thinking: false`（短答/测速必关）。 |

环境变量（补丁相关，在容器 env / 进程 env 生效）：

| env | 值 | 说明 |
|---|---|---|
| `STRATA_BF16_TC` | `1` | Turing FP16 张量核预填充（默认关需显式开）。 |
| `STRATA_SELECT_SIMT` | `2` | QSA FP32 评分器档位；1 为旧档（等价 0.1.40 本地补丁默认），2 为 #2071 增益档。 |
| `STRATA_PA_V2T` | `1` | int8 prompt attention v2（#2092，opt-in）。 |
| `STRATA_REFILL_PARTS` | `1` | 借槽回收走 GGUF pieces（#2078，opt-in）。 |
| `STRATA_PREFILL_HELP` | `1` | 层切分空闲卡分担短 prompt 专家流（≤~3.3K prompt 生效，4K 以上自动关）。 |
| `STRATA_ROUTE_TAIL_SKIP` | 默认 `7` | v0.1.43 新默认（`=0` 回退旧行为）。 |

## 5. 启动（容器化示例）

```bash
docker run -d --name strata --restart unless-stopped --gpus all --network host --ipc host \
  --ulimit memlock=-1 -e HOME=/path/to/home \
  -e STRATA_BF16_TC=1 -e STRATA_SELECT_SIMT=2 -e STRATA_PA_V2T=1 \
  -e STRATA_REFILL_PARTS=1 -e STRATA_PREFILL_HELP=1 \
  -v /path/to/strata:/path/to/strata \
  -v /path/to/Strata-data:/path/to/Strata-data \
  -v /path/to/weights:/path/to/weights \
  -v /usr/local/cuda-13.0:/usr/local/cuda-13.0:ro \
  <image> /path/to/strata/.venv/bin/python /path/to/strata/serve/server.py \
  --engine strata --config /path/to/strata/strata-iq3_s-dual-262k-vision.json --port 8000
```

- **镜像要求**：glibc 版本不低于宿主编译二进制的需求（参考引擎要求 GLIBC_2.43 → Debian sid 级基础镜像）；镜像内 Python 版本与 venv 一致（3.13）。
- **就绪判定**：`curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/v1/models` 轮询到 200；首启（读 48 GB 权重 + 填专家缓存）约 1.5–3 分钟，期间整机响应变慢属正常。
- **局域网开放**：配置 `host: 0.0.0.0`，可加 `api_key`（留空 = 免密，注意暴露风险）；API = OpenAI `/v1/chat/completions` + Anthropic `/v1/messages`。

## 6. 功能验收（部署完必做）

1. **短答确定性**：3 则固定短答（法国首都→巴黎；2+3→5；“床前明月光”接句）全部正确。
2. **针召回**：`tools/needle_bench.py --lengths 1k,32k,64k,128k --depths 10,50,90`（默认端口 8080，注意改 `--url`）；参考结果 12/12。必须关思考（`enable_thinking:false`）且 `max_tokens ≥ 40`（默认思考会吃掉 token，误判为召回失败）。
3. **长答口径**：温度 0 下长答非逐字确定（本引擎既有现象，非故障）→ 判据 = 内容稳定且正确，不做逐字 diff。
4. **视觉（如启用）**：生成含数字的 PNG → data URL 发送 → 比对数字（实测 4/4）。
5. **性能三点**：32K / 128K / 230K prefill 与 decode 与 §7 参考值同量级。

## 7. 性能基线与口径（参考机实测）

- **口径 A（客户端）**：prefill ≈ prompt_tokens / 首字墙钟；decode e2e = 完成 token / 全程墙钟（含提示读取，会低估 decode）。
- **口径 B（引擎日志，推荐）**：每请求一行 `done: N tokens in T s (R tok/s)` → R = 纯生成速率；读提示耗时 ≈ T − N/R。
- **参考数字**：v0.1.43 + 批次补丁，262K，pw2；fresh 读；计数类请求 2600 生成 token，2 次重复均值。

| Prompt 长度 | Prefill (tok/s) | Decode gen-only (tok/s) |
|---|---:|---:|
| 32K | ≈ 1.82k | ≈ 157 |
| 128K | ≈ 2.57k | ≈ 155 |
| 230K | ≈ 2.67k | ≈ 152 |

- 全长度曲线（500–230K，prefill/decode）见配套性能图；图内标注了测试协议与输出长度口径。
- decode 依任务形状浮动（草稿接受率相关，±10% 级）；测量须在空闲机上进行（单请求串行，多人用会排队）。

## 8. 已知坑（按踩坑优先级）

1. **永不设置 `CUDA_LAUNCH_BLOCKING=1`**：该变量本身会挂死 verify 窗口（上游已定性），也不能用它诊断崩溃。
2. **不要开 `STRATA_STAGE_PIN`**：曾默认开启并损坏 IQ3_S 长读后的 decode；现为 opt-in，保持不设。
3. **262K 是风险档**：上游同型机报告启动期 arena 耗尽（最坏冻结主机）→ 备 204800 档，冻结/启动 OOM 先降档复测。
4. **构建**：换版本先清 `build/`（CMakeCache 坑，见 §3）。
5. **前缀复用按 16384 块对齐**：同文档 B 请求 ≤16K 不命中属正常，不是缓存故障；测试设计要按块对齐取点。
6. **短答必须关思考**：否则 `max_tokens` 被思维链吃光，正文为空。
7. **冷启动首请求偶发挂起**：服务端看门狗会自愈；重启后建议先发一个小请求预热。
8. **单请求串行**：多客户端请求交替排队、聚合吞吐不叠加（本配置非多槽 batch 模式）。
9. **摘 PR 别用 merge、浅克隆先加深**：跨版本 PR 一律 cherry-pick 单提交；`git merge-base` 在浅历史下直接报错 → 先 `git fetch --deepen=600 origin`（见 §3.1）。

## 9. 升级与回滚

- **上游会重写历史** → 一律 `git fetch origin tag vX` + `git cherry-pick`（跨版本 PR 不要 merge，会把上游分叉整个拖进来）。
- **升级流程**：停服务 → 取码（v0.1.43 tag + §3.1 批次补丁）→ 清 `build/` + gcc-15 构建 → md5 + `BUILD.json` 守卫 → 起服务 → §6 功能验收 + §7 三点对照。
- **回滚**：引擎二进制 + `BUILD.json` 成对备份（一条命令切回）；改 env/参数前备份启动脚本与配置（`.bak-<日期>`）。
- **版本注意**：v0.1.43 = 本指南基线（新默认 `STRATA_ROUTE_TAIL_SKIP=7`，`=0` 回退）；sm_75 批次为补丁（截至 2026-10-12 未合入上游；上游合入后本批多数开关将默认生效）。

## 附录 A：完整启动参数（现产配置）

```bash
--pack /path/to/Strata-data/packs/iq3_s \
--native /path/to/weights/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf \
--ple-gguf /path/to/weights/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf \
--expert-profile /path/to/strata/data/expert-profile.bin \
--expert-cache auto --prefill auto:16384 --spec 4 --pipeline-windows 2 --spec-min-p 0.70 \
--mtp /path/to/Strata-data/mtp/rt --max-context 262144 --kv int8 --kv-resident 32768 \
--vision --vram-reserve-mib 700 --conversation-cache-mib 16384 --conversation-cache-slots 12
```

配置 JSON 顶层另有：`host: 0.0.0.0`、`port: 8000`、`layer_split: 26`、`gpu: [0,1]`、`reasoning_budget_tokens: 4000`、`vision.gpu: false`（视觉走 CPU）。

## 附录 B：本配置的实测备注

- **双卡建议 PCIe gen3 x8+x8 起**（更低链路会限制 32K prefill；参考机实测 x8 较 x4 快约 +14%）；NVLink 对本引擎无收益——层边界仅传激活，与 vLLM TP2 的刚需不同。
- **平台依赖**：prefill 由「显卡算力 × 链路带宽」决定，decode 受主机侧专家流带宽约束（更快 CPU/内存对 decode 收益明显大于 prefill）。
- **默认输出确定性**：温度 0 下短答确定；长答非逐字确定（见 §6.3）。
