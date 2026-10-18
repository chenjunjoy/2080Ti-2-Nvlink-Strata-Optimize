# 原始档案（备份存档）

本目录是 Strata 优化工作的**原始材料备份**，用于追溯复盘中的每一个结论。

## 来源与时间

| 归档目录 | 原始位置 | 说明 |
|---|---|---|
| `strata-ops/` | `/srv/share/strata-ops` | 部署文档、基准脚本、日志、基准结果、配置备份 |
| `engine-logs/` | `/srv/share/Strata/*.log` | Strata 引擎运行日志（IQ2_XS / Orca） |

归档日期：2026-10-19。

## 安全处理（重要）

- **已排除**：
  - `strata-ops/.hf_token`（HuggingFace token）
  - `strata-ops/strata-api-key.txt`（服务 API key）
- **已脱敏**：所有出现的真实 API key 已替换为 `<REDACTED>`，共 9 个文件：
  - `strata-ops/DEPLOY-NOTES.zh-CN.md`
  - `strata-ops/backups/` 下的 8 个配置备份
- 归档后已复查：API key 与 HF token 均无残留。

> 注意：`engine-logs/` 与 `results/` 中可能包含测试用的提示词与模型输出，仅作本机备份用途。

## 目录说明

```
archive/
├── README.md                      本文件
├── strata-ops/
│   ├── README.md                  运维索引
│   ├── DEPLOY-NOTES.zh-CN.md      部署与优化说明（已脱敏）
│   ├── BENCHMARK-vs-vLLM.zh-CN.md 速度对比
│   ├── PIPELINE-VALIDATION.zh-CN.md  pipeline-windows 验证报告
│   ├── QUALITY-vs-vLLM.zh-CN.md   质量对比
│   ├── *.py / *.sh                基准与驱动脚本
│   ├── logs/                      安装、校准、A/B 日志
│   ├── results/<日期>/            基准与质量原始输出
│   └── backups/                   配置备份（已脱敏）
└── engine-logs/
    ├── strata-iq2_xs.log
    └── strata-orca-iq3_xxs.log
```

## 与主复盘的关系

主文档 [`../README.md`](../README.md) 中的所有数字均可在本目录的日志/结果中找到出处：

- 校准与调优：`strata-ops/logs/strata-calibrate.log`、`strata-ops/logs/strata-ab*.log`
- pipeline A/B：`strata-ops/logs/pipeline-*.txt`、`strata-ops/logs/pipeline-*.log`
- vLLM 对比：`strata-ops/logs/bench*`、`strata-ops/results/`
- 配置演进：`strata-ops/backups/`
