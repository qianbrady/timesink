# timesink — terminal time review from your shell history

![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Tests](https://github.com/qianbrady/timesink/actions/workflows/ci.yml/badge.svg)
终端时间去向复盘：一条命令把 zsh / bash / PowerShell 的历史文件变成 Top-N 命令表、
24 小时时段热力图和自动化建议。纯 Python 标准库实现，零依赖、默认零网络。

## 解决什么问题

- 「一整天都在忙，时间到底花在哪了？」—— 历史文件里其实有答案：zsh 的
  `EXTENDED_HISTORY` 连每条命令的真实耗时都记了（`: <ts>:<elapsed>;<cmd>`）。
- PowerShell 与 bash 没有耗时，也能做频次分析；PowerShell 5.1 的
  `ConsoleHost_history.txt` 是 UTF-16 编码，timesink 的 BOM 嗅探自动处理。
- 重复劳动一眼可见：同一前缀（如 `git`、`npm run`）连续出现 ≥5 次时给出
  alias / 脚本化建议；可选接入 LLM 端点获得更具体的自动化建议，失败自动回退。

## 功能

| 功能 | 说明 |
|---|---|
| 三种历史格式 | zsh `EXTENDED_HISTORY`（含耗时）、bash `HISTTIMEFORMAT`（无耗时）、PowerShell 纯行（仅频次）；`--format` 可强制指定 |
| Top-N 命令表 | `--top` 默认 15；自动按总耗时（有耗时数据）或频次排序，`--sort time/freq` 可强制 |
| 24 小时热力条 | 有时间戳时输出 24 桶 ASCII 热力（`--tz utc` 默认，跨机器可复现；`--tz local` 本机时区） |
| 总追踪时长估算 | zsh 有 elapsed 字段时对耗时求和 |
| 建议引擎（规则式） | 同一命令前缀连续出现 ≥`--threshold`（默认 5）次 → 建议 alias 或脚本 |
| 可选 LLM 建议 | `--ai-endpoint` + `--ai-key` 走 OpenAI 兼容 chat API；任何失败回退规则引擎，不配置则完全离线 |
| 内置演示数据 | `--demo`（也是默认行为），确定性数据集跨午夜，方便直接看效果 |

## 安装

要求 Python ≥ 3.9，无任何第三方依赖。可装成命令，也可不装直接用模块。

```bash
git clone https://github.com/<you>/timesink.git
cd timesink
pip install -e .        # 可选：装成 timesink 命令；不装也能用 python -m timesink
```

## 30 秒快速开始

```bash
# 1) 内置演示数据（默认行为，一条命令看全貌）
python -m timesink

# 2) 真实历史：zsh（推荐，有耗时数据）
python -m timesink --file ~/.zsh_history

# 3) bash（HISTTIMEFORMAT，仅频次；若没配置 HISTTIMEFORMAT 会全部是一条命令）
python -m timesink --file ~/.bash_history

# 4) PowerShell（仅频次）
python -m timesink --file "$env:APPDATA\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt"

# 5) 常用参数
python -m timesink --file ~/.zsh_history --top 10 --sort time --threshold 5
```

### 示例输出（`python -m timesink`，内置演示数据，真实输出）

```
timesink 0.1.0 · 终端时间去向复盘
格式: zsh EXTENDED_HISTORY · 命令条数: 36
时间范围: 2022-12-31 22:00:00 UTC → 2023-01-01 02:15:00 UTC

追踪时长估算: 总计 1h39m07s（zsh elapsed 求和）

时段热力 24h（UTC，按耗时）:
▃▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁█▂
0   4   8   12  16  20
▁=最闲 █=最忙

Top 15 命令 · 排序: 总耗时
  #  COUNT   TOTAL      AVG    COMMAND
  1      1  20m00s    20m00s    python analysis.py
  2      2  13m00s    6m30s     python tools/gen_data.py
  3      1  10m00s    10m00s    pytest -q --slow
  4      9  8m38s     57s       git status
  ...

建议（规则引擎）:
  - `git` 连续执行 6 次（累计 6 次），且每次都是 `git status` → 建议配置 alias（如 `alias gs='git status'`）
  - 前缀 `npm` 连续出现 6 次（累计 6 次，含 2 种命令）→ 建议封装为脚本/工作流
```

### 输出去向

- 全部输出为纯文本（无 ANSI 转义），可直接 `>` 重定向到文件、进管道、贴聊天。
- 提示/警告走 stderr，不污染 stdout：`python -m timesink --file x.txt 2>/dev/null` 拿到干净报告。

## Roadmap

- [x] v0.1.0：三格式解析、Top-N、热力条、规则建议、可选 LLM、演示数据
- [ ] 命令归一化（折叠 `sudo `、路径参数），按「语义命令」聚合
- [ ] `--json` 结构化输出，方便接其他工具
- [ ] fish / nu history 解析
- [ ] 环比报告（两次运行 diff，看趋势）

## License

MIT — see [LICENSE](LICENSE) (Copyright (c) 2025 timesink contributors).

## Usage

```text
$ python -m tests --help
C:\Users\Brady\AppData\Local\Programs\Python\Python314\python.exe: No module named tests.__main__; 'tests' is a package and cannot be directly executed
```

## Contributing

Issues and PRs welcome - run `pytest` locally before submitting.
