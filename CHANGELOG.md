# Changelog

## v0.1.0 (2025-06-01)

- 首个可用版本：终端时间去向复盘 CLI（Python 纯标准库，零依赖零网络默认）。
- 支持三种历史格式解析（自动识别，也可 `--format` 强制）：
  - zsh `EXTENDED_HISTORY`（`: <ts>:<elapsed>;<cmd>`，含耗时）
  - bash `HISTTIMEFORMAT`（`#<ts>` + 命令两行一组，无耗时）
  - PowerShell `ConsoleHost_history.txt`（纯行，仅频次模式；自动处理 UTF-16 BOM）
- 输出：Top-N 命令表（`--top` 默认 15，按总耗时或频次排序）、24 小时时段 ASCII 热力条
  （有时间戳时）、总追踪时长估算（zsh 有 elapsed 时）。
- 规则式建议引擎：同一命令前缀连续出现 ≥5 次（`--threshold` 可调）→ 建议 alias 或脚本化。
- 可选 `--ai-endpoint/--ai-key` 让 LLM 对 Top 命令给自动化建议，失败自动回退规则引擎，
  不配置则完全离线。
- `--demo` 内置确定性演示数据集（跨午夜时段，便于查看热力图与建议触发）。