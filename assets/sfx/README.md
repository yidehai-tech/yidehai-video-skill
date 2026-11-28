# 内置离线 CC0 UI 微音效包 (`assets/sfx/`)

这里的 5 个短音效专门服务于 `scripts/motion_templates.py` 生成的 3 套动效片母版（`split_compare`、`pack_archive`、`ranking`），均由 `scripts/sfx_manager.py` 使用纯 Python 标准库确定性声学合成（**CC0 无版权风险、零联网、零代理、48 kHz 16-bit PCM WAV**）：

| 文件名 | 时长 | 听感与动效卡点用途 |
| :--- | :---: | :--- |
| `whoosh.wav` | 0.28s | 轻柔空气扫风：总卡一分为二、卡片抬升入袋、榜单整卡入场 |
| `pop.wav` | 0.11s | 清脆微气泡弹出：卡片出现、榜单条目落位、结尾信息条提示 |
| `ding.wav` | 0.38s | 温润玻璃马林巴双音：可收项勾选、`✓ 已入袋` 确认、要点提示条 |
| `tap.wav` | 0.14s | 沉稳木质轻敲：VS 胶囊定格、红卡「不收」红线划掉 |
| `chime.wav` | 0.56s | 达成和弦印章音：凑够 5kg / 3件起收盖章、TOP 1 揭晓、总结收尾 |

## 自定义替换音色

- 想换成自己喜欢的真实录制 CC0 音效（例如用外部音源挑选的试听文件），只需将同名 `<name>.wav` 或 `<name>.mp3` 直接覆盖放进本目录，`sfx_manager.py` 与 `batch_runner.py` 会自动优先读取。
- 如需恢复默认内置音色，运行一次 `python3 scripts/sfx_manager.py --generate --overwrite` 即可无损重建。
