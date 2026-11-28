# 动效片实战手册（单条与批量通用：浅色配色 / 底版复用 / 有声混音）

> **适用时机**：**单条和批量出 `动效片` 均必读**（2026-11-27 实测教训：不仅批量出 ≥3 条，单条演示时裸复用深绿底版同样会被主编判定太丑返工！）。
> **来源**：2026-11-24 & 2026-11-27 真实用户反馈修订——深绿底太闷、无声静默被主编打回。
> **优先级**：`01-brand-rules.md` 为最高优先级硬红线；本手册与 `04-visual-style.md`（配色）、`06-rendering-playbook.md`（渲染质检）配合执行。

---

## 一、开工前三条硬检查（单条与批量通用，缺一即返工）

1. **禁止深绿裸底，强制浅色配色**：**无论单条还是批量，深森林绿 `#102A22` 严禁作为整屏背景使用！** 单条优先直接用内置 5 套浅色主题的 `scripts/motion_templates.py`（或任选一套浅色主题注入）；批量 ≥3 条必须按顺序轮换 5 套浅色主题，相邻两条主色相不同。规则见 `04-visual-style.md` §2.1–2.2。
2. **音频默认有声**：默认成片 = 中文旁白（该形态有旁白时）+ EBU R128 响度归一化真实无版权 BGM（**人声 `-14 LUFS` + BGM `-16 LUFS × 18%`**）；**无声版是可选产物，不是默认**。自写渲染脚本时**严禁绕开 `batch_runner.py` 的配乐逻辑**（否则成片静音）；缺少真实音源时直接报错拦截，绝不跳过产出无声半成品。
3. **形态讲清楚**：`动效片` 是「多屏图形动效 + **AI 旁白**」，默认有声版但**非真人出镜**；若要真人出镜口播，请改用 `口播包装` / `实拍混剪`。交付时一句话说明，避免主编按「动效片＝真人出镜口播视频」预期。

---

## 二、配色轮换与主题注入

### 2.1 五套浅色主题

直接取 `04-visual-style.md` §2.2 的色值表，按条目顺序轮换（暖米橙 → 浅雾青 → 暖杏陶 → 浅暖金 → 淡薄荷）。字段：`bg1/bg2/bg3` 整屏渐变、`stage1/stage2` 信息卡渐变、`ink` 主文字、`accent/accent2` 强调、`tag` 小标签、`glow` 光晕。

### 2.2 重大坑：子合成 CSS 覆盖选择器

给 `compositions/film.html` 注入主题覆盖 CSS 时，`#main .tline1{...!important}` **完全不生效**：

- `#main` 位于 root 的 `index.html`，子合成元素**不在 `#main` 子树内**；
- `:root` 变量、`#main{自身背景}` 生效，**任何 `#main .xxx` 后代选择器都不生效**。

✅ 正确做法：覆盖规则一律用**纯 class 选择器 + `!important`**；颜色尽量走 `:root` 变量。
❌ 症状：标题白字融进米白底、舞台仍是深绿、顶部徽章还是绿底。

### 2.3 可直接复制的覆盖 CSS 模板

把下面这段插进 `film.html` **原 `<style>` 块的 `</style>` 之前**（同一 style 块内，后定义者胜）：

```css
:root{--bg:BG2;--bg2:BG3;--ink:INK;--accent:ACC;--mint:ACC;--soft:TAG;
      --line:rgba(22,48,38,.13);--panel:rgba(22,48,38,.05)}
#main{background:radial-gradient(120% 70% at 50% 6%,BG1 0%,BG2 46%,BG3 100%)!important;color:INK!important}
.grain{opacity:.22!important}
.glow.a{background:radial-gradient(circle,GLOW,transparent 70%)!important}
.tline1{color:INK!important;text-shadow:0 3px 0 rgba(255,255,255,.80)!important}
.tline2{color:ACC!important;text-shadow:none!important}
.trule{background:linear-gradient(90deg,ACC,ACC2)!important}
.tbadge{background:rgba(22,48,38,.88)!important;color:#FFFFFF!important}
.tag{color:TAG!important;opacity:.82!important}
.stage{background:linear-gradient(155deg,STAGE1,STAGE2)!important;
  border-color:rgba(22,48,38,.10)!important;
  box-shadow:0 30px 70px rgba(22,48,38,.14),inset 0 2px 0 rgba(255,255,255,.90)!important}
.stage-floor{background:linear-gradient(180deg,rgba(255,255,255,0),ACC2_20PCT)!important}
.cap{background:rgba(16,38,29,.88)!important;color:#FFFFFF!important}
.cap.hi{background:ACC!important;color:#FFFFFF!important}
.step-badge,.burst,.num-chip{color:#FFFFFF!important}
.bigword{color:ACC!important}
```

### 2.4 底版硬编码与封面的字符串映射

- 底版 `<style>` 里的暖黄系必须字符串替换成主题色，否则残留黄色块：
  `#FFD43B → ACC`、`#FFE9A8 / #FFE990 / #FFF1AE / #FFF0A0 / #D7C58E → ACC2`、`#8C7B4C → ACC`。
- 封面模板（`render_poster.py` 同款 `COVER_HTML`）**无 CSS 变量**，需整套字符串映射：
  `body` 深绿径向渐变 → `bg1/bg2/bg3`；`color:#FFFFFF` → `INK`；`#FFD43B` → `ACC`；`#FFF0A0` → `ACC2`；`#CDE8D9` → `INK`；
  胶囊底 `rgba(47,158,68,.90)` → `rgba(22,48,38,.88)`；小卡白半透明底 → `#FFFFFF → stage2`；`.l1` 白字黑影 → `INK` + 白影；`.grain` 白线 → 深色细线。
- 深色插画（衣柜、秤盘、卡片）**保留**，作浅底上的视觉锚点，实测对比清晰，不要一起改浅。

---

## 三、有声版合成（旁白 + BGM）

### 3.1 中文旁白

```python
import asyncio, edge_tts
asyncio.run(edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural", rate="+10%").save("voice.mp3"))
```

- 文案 **40–55 字**，覆盖 4 屏信息，口语化、过 `01-brand-rules.md` 禁用词（0 命中）。
- 合成后用 `atempo = max(1.0, voice_duration / 9.4)` 压进 **9.4 秒**，给收尾留 0.6 秒纯音乐。

### 3.2 真实无版权 BGM

音源优先级：`.yidehai/cache/bgm/` 已缓存真实无版权音源 → 在线免版权源（如 `media-catalog.json` / Jamendo）→ `.yidehai/config.json` 免版权目录。
> 若选用 Jamendo CC Standard 等附带署名要求的曲目，**务必在发布文案与交接备注中保留作者/曲目署名**。

```sh
ffmpeg -y -v error -ss START -t 10 -i bgm.mp3 \
  -af "afade=t=in:st=0:d=0.6,afade=t=out:st=9.1:d=0.9,volume=0.12" \
  -ac 2 -ar 48000 bgm_10s.wav
```

- 批量时**每条错开起点**（本机实测 18 / 72 / 128 / 186 / 244 秒），避免 5 条听起来一样。
- 音量 **12%**，0.6 秒淡入 / 0.9 秒淡出。

### 3.3 混音（无声 mp4 + 旁白 + BGM → 有声版）

```sh
ffmpeg -y -v error -i silent.mp4 -i voice.mp3 -i bgm_10s.wav \
  -filter_complex "[1:a]aresample=48000,atempo=TEMPO,volume=1.10,apad,atrim=0:9.6[v];\
[2:a]aresample=48000,volume=1.0[b];\
[v][b]amix=inputs=2:normalize=0:duration=longest:dropout_transition=0,alimiter=limit=0.95[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -t 10 -movflags +faststart voiced.mp4
```

- `amix normalize=0` 必须显式指定，否则两路音量被再减半。
- `alimiter=limit=0.95` 防削波；`-c:v copy` 不重编码画面。
- 验收：`ffprobe` 确认含音轨、时长 10.000s；`volumedetect` mean 约 −18～−20 dB、max 不削波（本机实测 mean −18.5～−19.2 dB）。

### 3.4 内置离线 UI 卡点微音效（`assets/sfx/`）

- 仓库内置 5 个纯离线 CC0 轻音效（`whoosh` 切卡、`pop` 弹出、`ding` 入袋确认、`tap` 划掉轻敲、`chime` 达标印章）。
- `motion_templates.py` 会按 GSAP 动画关键帧秒数自动输出 `sfx_cues.json`，`batch_runner.py` 混音时自动叠加（人声旁白存在时 SFX 系数 `0.38`，无旁白纯 BGM 时 `0.52`，绝不盖过台词）。
- 如需单条禁用可在条目 JSON 设 `"sfx": false`；如需自定义音色，直接将同名 `<name>.wav` 或 `<name>.mp3` 放入 `assets/sfx/` 即可替换。

### 3.5 双版本与署名

- `{slug}.mp4` = **有声版**（默认发布用）；`{slug}-无声版.mp4` = 同配色无声版（改挂平台热门音乐时用，规避跨平台版权静音）。
- BGM 带署名要求时，**发布文案与交接备注必须写明署名**。
- 含 AI 生成画面 + AI 合成配音，发布勾选「AI 生成」声明。

---

## 四、渲染稳定性：优先用 `motion_templates.py` 或浅色改版旧底版

- **不要从零自写 CSS `@keyframes` 动效工程**：在 HyperFrames 的 seek 下只有第 1 屏有画面，后续屏全空；内联 delay → class delay、ID 级规则、scene 前缀 ID、去 opacity 基类、加 stage 动画均试过无效。
- **优先直接使用已内置 7 套 MotionFace 风格新母版（`split_compare` 一卡拆两类 / `pack_archive` 卡片归档 / `ranking` 排名攀升 / `step_flow` 三步流程 / `myth_flip` 误区反转 / `metric_spotlight` 大数字聚焦 / `prep_memo` 打包便签）× 5 套浅色主题（35 种视觉组合）的 `scripts/motion_templates.py`**；若要复用本机已出过片的 OpenMotion 历史底版（旧羽绒服 A / 打包3件事 B / 怕坑秤 C，其中部分底版原版为深绿背景）：
  - **【强制硬规 · 单条也不例外】复用旧底版后，必须按上方第二节 2.3/2.4 注入 5 套浅色主题之一替换整屏背景！** 严禁偷懒保留 `#102A22` 深绿裸背景直接出片；
  - 按 `data-hf-id` 精确替换文案 + 删品牌浮条块 + **同步改 `index.html` 的 `data-composition-variables` 默认值**（否则标题仍是旧文案）。
- 带红色删除线的节点替换时保持「被划掉」语义（如「留着占窝」），写反会变成「都不用自己扛」被划掉。
- 顺序：`lint-project.mjs` 0 错 0 警 → `hyperframes render` **前台同步** → 抽 `0.2 / 1.2 / 3.0 / 6.2 / 8.8 / 9.6` 秒逐帧看。
- 追加覆盖 CSS **不影响 GSAP 时间轴**，只改颜色，已验证渲染正常。

---

## 五、交付结构与质检清单

```
output/动效片批量N条-YYYYMMDD/
├── V00N-选题词/
│   ├── {slug}.mp4                 # 有声版（旁白 -14 LUFS + BGM -16 LUFS×18%）
│   ├── {slug}-无声版.mp4          # 同配色，平台挂载音乐用
│   ├── cover-9x16.jpg
│   └── cover-3x4.jpg
├── review.html                   # 审片台：视频 controls 不要 muted，标注主题 / 口播 / BGM 署名
├── 发布文案汇总.md                # 6 平台文案 + 口播全文 + BGM 署名 + AI 声明
├── results.json
└── _qc/                          # 每条 6 帧联系表 + 封面总览
```

交付前逐项过：

- [ ] 5 条主色相各不相同、浅底深字、无大面积深绿 / 满屏暖黄；
- [ ] 中文无乱码孤字、无裁切重叠、首帧饱满、四屏动效正常；
- [ ] 无底部品牌浮条、无全屏静态尾卡；
- [ ] 双封面与成片同主题，两行大字与图形不重叠，3:4 版居中在中间 60%；
- [ ] 有声版含音轨且 10.000s、旁白不吞字、BGM 不盖人声；无声版为主动选择；
- [ ] 禁用词 0 命中；BGM 署名、AI 生成声明已写入交付说明。

---

## 六、内置脚本对齐

仓库内置的 `scripts/batch_runner.py`（动效片批量混音与旁白）与 `scripts/package_ai_video.py`（AI/实拍包装默认按 EBU R128 `-14 LUFS` 旁白 + `-16 LUFS × 18%` BGM 混入真实无版权 BGM）已对齐上述防削波与响度标准，直接调用即可，无需每台电脑单独维护自定义脚本。
