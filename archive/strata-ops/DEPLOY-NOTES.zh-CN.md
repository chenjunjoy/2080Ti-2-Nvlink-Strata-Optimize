# Strata 本机部署与优化说明

## 位置
- 程序:`/srv/share/Strata`(2TB 硬盘 `/dev/nvme1n1p1` 根目录,挂载点 `/srv/share`)
- 数据:`/srv/share/Strata-data`(约 73 GB)
- 已装模型:`IQ2_XS`(Qwen3.8-Flash-Next,131072 上下文,支持图片)
- 硬件:2 × RTX 2080 Ti(22 GB,分层 0-22 / 23-47),76 GB 内存

## 启动 / 停止(systemd 服务,与 vLLM 对等)
Strata 和 vLLM **都做成 systemd 服务,但都未设开机自启**,需要时手动启动。
两者 `Conflicts`(启动一个会自动停另一个),避免同时抢显存。

```bash
sudo systemctl start  strata     # 启动 Strata(加载约 1-2 分钟)
sudo systemctl stop   strata     # 停止
sudo systemctl status strata     # 状态 / 日志
journalctl -u strata -f          # 实时日志

sudo systemctl start  vllm       # 改用 vLLM(会自动停掉 Strata)
sudo systemctl stop   vllm
```

- 服务定义:`/etc/systemd/system/strata.service`、`/etc/systemd/system/vllm.service`
- 运行脚本:`/home/jim/scripts/strata-run.sh`
- 也可不开服务,直接前台跑:`cd /srv/share/Strata && ./run-iq2_xs.sh`
- 更新程序(不启动):`cd /srv/share/Strata && ./update.sh`
- **当前两个服务都 `disabled`**(不开机自启)。若想开机自启其一:
  `sudo systemctl enable strata`(或 `vllm`)。

首次/重启加载模型约 1-2 分钟,期间机器会卡顿,属正常。

## 访问
- 本机浏览器:`http://127.0.0.1:8080`
- 局域网:`http://192.168.1.13:8080`(机器有 mihomo 代理,服务自报的 198.18.0.1 是代理虚拟网卡,勿用)
- OpenAI 兼容 base URL:`http://192.168.1.13:8080/v1`(Anthropic:`/v1/messages`)
- API key:`<REDACTED>`(见 `/srv/share/strata-ops/strata-api-key.txt`;服务监听 0.0.0.0,**务必保留密钥**)

## 已应用的优化
| 项 | 值 | 效果 |
|---|---|---|
| `--pcie-frac` | `1.00` | `--calibrate` 实测选定 |
| `--spec-min-p` | `0.70` | 同上 |
| `STRATA_SPLIT_MTP_BATCH` | `1` | prefill +3% |

**实测(单请求):** decode 82.7 → **87.8 tok/s(+6.2%)**;prefill(6K)881.6 → **910.0 tok/s(+3.2%)**。

## 已否决的开关(本机实测无收益或有害)
`pipeline_windows_2`(decode −10.8%,PCIe 3.0 x8 窄链路所致)、`kv_k8v4`(−3%)、
`prefill_help`(±0%)、`pf_fused`(±0%)、`layer_split 20`(±0%)。

> decode 已接近本机硬件上限(瓶颈:2080 Ti 算力 + PCIe 3.0 x8)。
> 想再快只能换更小规格,如 `./setup.sh --setup --model Q2_0`(约 +10%,质量略降)。

## 配置文件
- 模型配置:`/srv/share/Strata/strata-iq2_xs.json`(含 `env` 与调优参数)
- 调优前备份:`/srv/share/strata-ops/backups/strata-iq2_xs.json.prestart`;调优基准:`/srv/share/strata-ops/backups/strata-iq2_xs.json.tuned`
- 速度基准脚本:`/srv/share/strata-ops/strata-bench.py`(用法:`python3 /srv/share/strata-ops/strata-bench.py 标签 3`)
- 本目录索引:`/srv/share/strata-ops/README.md`

## 安全提醒
- API key 与你之前的系统登录密码是同一串,且服务对局域网开放 —— 建议**更换为独立的随机长密钥**,并修改系统密码。

---
生成于 2026-10-15。
