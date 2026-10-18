# strata-ops — Strata 本机运维与基准文件

这里是部署 Strata 过程中产生的**脚本、日志、基准结果、备份和说明文档**的集中目录。
(部署本体不在本目录:程序在 `/srv/share/Strata`,模型数据在 `/srv/share/Strata-data`。)

## 目录结构
```
strata-ops/
├── README.md                       本文件
├── strata-api-key.txt              API key(权限 600)
├── DEPLOY-NOTES.zh-CN.md           部署与优化总说明、服务管理
├── BENCHMARK-vs-vLLM.zh-CN.md      速度对比(Strata vs vLLM)
├── QUALITY-vs-vLLM.zh-CN.md        质量对比
├── strata-bench.py                 单请求速度基准(配合运行中的服务)
├── llm-bench.py                    通用流式基准(任意 OpenAI 兼容服务)
├── quality-bench.py                质量对比(6 道题)
├── strata-ab.py / strata-ab2.py    A/B 测试脚本(历史)
├── install-strata-models.sh        初始安装脚本(历史)
├── logs/                           安装/校准/A-B 日志
├── results/<日期>/                 基准结果与质量原始输出(按日期归档)
└── backups/                        配置备份(.prestart / .tuned)
```

## 切换 Strata / vLLM 速查
两者都**独占两张 GPU,不能同时运行**;两个服务已设 `Conflicts`,启动一个会自动停另一个。
两者都**未设开机自启**,需要时手动启动。

```bash
# —— 切到 Strata ——
sudo systemctl start strata          # 自动停掉 vLLM
# 就绪: http://192.168.1.13:8080    (本机 127.0.0.1:8080)
# 需 API key: 见本目录 strata-api-key.txt

# —— 切到 vLLM ——
sudo systemctl start vllm            # 自动停掉 Strata
# 就绪: http://192.168.1.13:8000/v1  (无需 key)

# —— 查看 / 停止 / 日志 ——
sudo systemctl status  strata
sudo systemctl stop    strata
journalctl -u strata -f
```

| | Strata | vLLM |
|---|---|---|
| 模型 | Qwen3.8-Flash-Next IQ2_XS(125B MoE) | Qwen3.8-27B-NVFP4(27B) |
| 上下文 | 131072 | 262144 |
| decode | ~84 tok/s | ~76 tok/s |
| 端口 / 鉴权 | 8080 / 需 key | 8000 / 无 |
| 命令 | `systemctl … strata` | `systemctl … vllm` |

选用建议见 `BENCHMARK-vs-vLLM.zh-CN.md` 与 `QUALITY-vs-vLLM.zh-CN.md`。

## 常用命令
```bash
# 速度基准(需服务在运行)
python3 /srv/share/strata-ops/strata-bench.py 标签 3

# 想开机自启其一(当前都未启用)
sudo systemctl enable strata         # 或 vllm
```

> 脚本内部路径均为**相对脚本自身位置**,整个目录可安全移动。
