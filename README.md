# yidehai-video

![Version](https://img.shields.io/badge/version-3.0.0-2B8A3E)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-blue)
![Workspace](https://img.shields.io/badge/Agent%20Workspace-AGENTS.md-orange)

面向 **亿德海（yidehai）旧衣回收** 垂直场景的 **独立项目级 AI 短视频生产工作台**（专为团队非技术同学打造）。  
从 `v3.0.0` 起彻底告别全局 Skill 挂载与跨工具目录同步坑：**把本项目文件夹下载到电脑上，在任意桌面 AI 工具里打开这个文件夹即可直接出片**。内置业务事实库、多平台合规硬拦截、四维选题防枯竭矩阵、全局素材防重账本与跨平台渲染管线。

> **致 AI 助手（首次部署 / 旧版升级自动执行指令，禁止二次确认）**：  
> 当用户把本仓库链接或本文件发给你并让你「装好 / 初始化 / 从旧版升级」时，请一次性连续完成：  
> 1. 若当前目录不是 `yidehai-video` Git 仓库，请克隆到独立持久文件夹（推荐桌面或文档目录 `yidehai-video`），**严禁删除用户原业务文件夹里已有的历史成片与素材**；若已是本仓库则执行 `git pull`；  
> 2. 进入 `yidehai-video` 目录立刻运行 `python3 scripts/setup_project.py`（从 v2.x 旧版升级时加 `--cleanup-legacy-skills` 并附带 `--extra-skills-dir` 清理自身私有技能残留；若原业务文件夹存在旧的 `.agents/skills/yidehai-video` 或 `.skills/yidehai-video` 软链/托管副本，也一并安全移除）；  
> 3. **严禁装完文件后停下来反问用户「要不要安装 FFmpeg / edge-tts」**；直接输出核对后的新项目文件夹路径、`outputs/dashboard.html` 路径，并提示用户后续打开该文件夹按根目录 [`AGENTS.md`](AGENTS.md) 对话出片（不要打印任何密钥明文）。

---

## 核心特性

- **开箱即用的项目级结构**：所有桌面 AI 工具（**WorkBuddy、豆包桌面版、Claude Code、Codex、Cursor、Antigravity、OpenClaw** 等）打开本项目文件夹即自动读取根目录 [`AGENTS.md`](AGENTS.md) / [`CLAUDE.md`](CLAUDE.md)，无需安装全局 Skill、不污染其他项目。
- **老用户（v2.x 全局 Skill）无损平滑升级**：首次运行会自动把本机旧版 `~/.yidehai-video/` 中的 API Key、本地素材目录、防重账本（`used_history.json`）、任务台账（`tasks.json`）、已下载缓存与 Windows FFmpeg **自动、无损、幂等地迁入本项目 `.yidehai/`**，原目录完整保留作备份。
- **11 大生产轨道统一调度**：覆盖 0 成本高频日更（`大字报` / `动效片` / `实拍混剪` / `实拍快剪` / `前后对比片` / `口播包装`）、一鱼两吃（`图文故事片`）、宿主内置 AI 省钱路线（**`宿主AI片`**）与付费高拟真 AI 视频（`即梦片` / `Flow片` / `API片`）。
- **全平台 Agent 自动分级适配**：自动识别运行环境（L1 桌面执行型 / L2 轻沙箱型 / L3 纯对话知识库型），有终端自动渲染出片，纯对话直接产出满血合规脚本与防穿帮 Prompt。
- **积分与费用自主选择护栏**：默认仅使用 0 积分免费轨道；调用宿主内置生图/生视频、即梦 CLI、Google Flow 或云端视频 API 前均要求显式选择与确认，并具备提交前原子落盘防重复扣费机制。
- **统一成片质量标准**：默认启用 EBU R128 响度归一化混音（有旁白轨道：**人声 `-14 LUFS` + 真实无版权 BGM `-16 LUFS × 18%`**；`大字报`：**`-16 LUFS × 0.85`**）、无底部品牌浮条与全屏静态尾卡、自动产出 `9:16` + `3:4` 双封面与 8 帧质检联系图。
- **本机配置隔离与可见仪表盘**：隐私密钥、素材目录、防重账本与任务台账全部持久化在已 gitignore 的 `.yidehai/`；成片与可双击查看的离线统计仪表盘统一输出到 **`outputs/dashboard.html`**。

---

## 支持的视频形态

| 形态 | 标识 | 费用口径 | 旁白 | 底层管线 | 适用场景 |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **`大字报`** | `poster` | 免费（0 点） | ✕ | `render_poster.py`（离线直出） | 8.8s 风景空镜 + 分段高亮/逐层浮现大字报，高频日更主力 |
| **`动效片`** | `motion` | 免费（0 点） | ✓（AI） | OpenMotion / HyperFrames | 10s 多屏卡片动效 · 7 套 MotionFace 风格母版 × 5 套浅色主题轮换 |
| **`实拍混剪`** | `montage` | 免费（0 点） | ✓（AI） | `package_ai_video.py` + HeyGen HyperFrames | 3 段本地实拍视频/图片防重拼接 + 干声旁白 |
| **`实拍快剪`** | `fastcut` | 免费（0 点） | ✓（AI） | `render_footage_video.py`（离线零浏览器） | 6–8 个 1.2–2.0s 快切实拍短镜头 + 卡点字幕 |
| **`前后对比片`** | `before_after` | 免费（0 点） | ✓（AI） | `render_footage_video.py`（离线零浏览器） | 上下分屏对比（清理前 vs 清空后徽章）+ 强共鸣口播 |
| **`图文故事片`** | `storybook` | 按图源定（可 0 点） | ✓（AI） | `storybook_builder.py` + HeyGen HyperFrames | 4–6 张分镜图平滑推镜成片 + **小红书 3:4 轮播套图** |
| **`宿主AI片`** | `host_video` | 0 外部 API 费（耗宿主额度） | ✓ | 当前 Agent 内置生视频 + HeyGen HyperFrames | 复用豆包/WorkBuddy/千问/扣子自带生视频能力省外部成本 |
| **`即梦片`** | `dreamina` | 扣即梦积分（Opt-in） | ✓ | `dreamina_runner.py` + HeyGen HyperFrames | 纯即梦口播或「即梦 5s 开场 + 本地实拍」省积分混剪 |
| **`Flow片`** | `flow` | 扣 Google 点数（Opt-in） | ✓ | `ego-lite` + Google Flow + HeyGen HyperFrames | `Omni 1.2 Flash` 口播或 `Veo 3.1 Lite` 10 点省点混剪 |
| **`API片`** | `api_video` | 扣聚合 API 余额（Opt-in） | ✓ | `api_video_runner.py` + HeyGen HyperFrames | 纯 HTTP 零浏览器直出 `Omni 1.2` / 豆包 `sd-2.0/2.5` / `MiniMax-H3` / `Veo 3.1` / `Kling` |
| **`口播包装`** | `motiongit` | 免费（0 点） | ✓（原声） | MotionGit 官方免费模板 | 真人实拍口播视频的高质感动态风格化包装 |

---

## 快速开始（非技术同学 2 步上手 · 无需敲命令）

### 方式 A：新同学首次使用（复制这段话发给 AI 即可）

1. **让 AI 自动下载并初始化（只需做一次）**：打开任意桌面 AI 工具（WorkBuddy / 豆包桌面版 / Claude Code / Codex / Cursor / Antigravity），直接发送：
   ```text
   请帮我把 https://github.com/yidehai-tech/yidehai-video 下载到我电脑的文档目录（文件夹名 yidehai-video），然后立刻进入该目录运行 python3 scripts/setup_project.py 一次性装好基础环境（不要中途停下来反复确认）。完成后把文件夹路径发给我。
   ```
   > *(开发者可选命令行：`git clone https://github.com/yidehai-tech/yidehai-video.git && cd yidehai-video && python3 scripts/setup_project.py`)*
2. **打开文件夹直接出片**：在 AI 工具里点 **「打开文件夹」→ 选中刚下好的 `yidehai-video` 文件夹**，以后每次做视频都打开这个文件夹直接对话即可。

### 方式 B：老同学（已建过文件夹 / 装过 v2.x 旧 Skill）平滑升级

如果你之前在电脑上建过出片文件夹、装过旧版全局 Skill 并配置过素材目录、API Key 或已有防重记录，直接在你正在用的 AI 工具里发送下面这段话（无需手动敲命令）：

```text
yidehai-video 已经升级到 v3.0.0 项目级工作台（仓库地址：https://github.com/yidehai-tech/yidehai-video），以后不再作为全局 Skill 使用，而是直接打开项目文件夹就能出片。

请帮我一次性完成平滑升级，不要中途反复确认：
1. 获取新版项目：如果当前文件夹本身就是 yidehai-video 的 Git 仓库，直接 git pull 更新到最新版；如果当前只是之前挂载过旧 Skill 的普通文件夹，请把最新版仓库克隆到一个独立的新文件夹（比如桌面或文档下的 yidehai-video），绝对不要删除我原文件夹里之前做好的视频和素材。
2. 一键迁移旧配置 + 清理旧全局 Skill：进入新版 yidehai-video 目录运行 python3 scripts/setup_project.py --cleanup-legacy-skills（如果当前工具还有自己的私有技能目录，一并加上 --extra-skills-dir 清理掉旧版 yidehai-video / yidehai-video-skill 残留；若原业务文件夹里有旧的 .agents/skills/yidehai-video 或 .skills/yidehai-video 托管副本/软链，也安全清理掉）。
3. 确认结果：迁移完成后，运行 python3 scripts/media_manager.py config --show 和 python3 scripts/task_tracker.py summary 帮我核对旧配置（API Key、素材目录、防重记录、历史任务）是否都已无损迁入新项目的 .yidehai/（保留 ~/.yidehai-video/ 原目录作备份，不要打印密钥明文）。
4. 最后告诉我新版 yidehai-video 文件夹的完整路径以及 outputs/dashboard.html 的路径——之后我就在这个 AI 工具里直接打开这个新版文件夹开始出片。
```

> **免手动兜底**：即使忘记先跑初始化，首次运行任意出片或 `preflight` / `config` / `summary` 命令时，系统也会静默自动完成 `~/.yidehai-video/` 到 `.yidehai/` 的无损迁移与路径重写。

### 方式 C：纯对话 / 知识库型 Agent 接入（豆包网页版、通义千问、Kimi、扣子等）

无本地终端环境的工具，下载本仓库压缩包后将根目录的 `AGENTS.md` 与 `knowledge/01–11` 导入对应智能体或项目知识库，直接发送：
```text
帮我出一套换季清衣柜的旧衣回收短视频方案，包含合规脚本、9:16 和 3:4 双封面大字、6 平台发布文案，以及可以直接粘贴到即梦/剪映的提示词。
```

---

## 常用对话指令（打开项目文件夹后直接说）

AI 会自动加载根目录 [`AGENTS.md`](AGENTS.md)，团队同学只需用大白话提需求：

- **单条 0 成本日更（最常用）**：`帮我做一条换季清衣柜的大字报视频` / `帮我做一条旧衣回收避坑指南的动效片`
- **批量出片**：`帮我批量生成 20 条旧衣回收视频`（默认 50% 大字报 + 50% 动效片，0 积分）
- **本地实拍出片**：`用我的本地实拍素材做一条实拍快剪` / `做一条前后对比片`
- **视频 + 小红书轮播一鱼两吃**：`帮我做一条旧羽绒服回收的图文故事片`
- **查看统计与历史记录**：`看看今天出了几条视频，把统计面板发我`（双击 `outputs/dashboard.html` 即可离线查看）
- **同步最新版**：`更新一下 yidehai-video`

> **首次补配置说明**：第一次出某种类型的视频时，如果缺风景空镜源、BGM 源或本地实拍文件夹，AI 会主动停下来一次性问你补充（直接把本地素材文件夹路径或免费 Key 发给 AI 即可），之后会永久记住在 `.yidehai/config.json` 中。

---

## 开发者配置与常用 CLI（参考 `config.example.json`）

首次出片前如果缺少某类素材源或 Key，`preflight` 门禁会自动拦停并一次性提示补充；所有配置保存在 `.yidehai/config.json`（永不入库）：

```bash
# 查看当前项目配置（自动脱敏，不回显密钥明文）
python3 scripts/media_manager.py config --show

# 校验目标轨道所需配置是否齐备
python3 scripts/media_manager.py preflight --track poster

# 手动触发预览/合并旧版 ~/.yidehai-video/ 数据（一般会自动执行）
python3 scripts/media_manager.py migrate --dry-run

# 配置大字报风景空镜（Pexels / Pixabay 免费 API Key 或本地空镜目录二选一，必配）
python3 scripts/media_manager.py config --set-pexels-key "<YOUR_PEXELS_KEY>"
python3 scripts/media_manager.py config --add-bg-dir "/path/to/scenic"

# 配置背景音乐源（Jamendo 免费音乐 Client ID 或本地免版权音乐目录）
python3 scripts/media_manager.py config --set-jamendo-id "<YOUR_JAMENDO_CLIENT_ID>"
python3 scripts/media_manager.py config --add-bgm-dir "/path/to/bgm"

# 配置本地业务实拍目录（供实拍混剪 / 实拍快剪 / 前后对比片 / 省点混剪防重抽取）
python3 scripts/media_manager.py config --add-footage-dir "/path/to/footage"

# 查看跨 Agent 共享任务台账与待续渲列表（双击 outputs/dashboard.html 可离线看图表）
python3 scripts/task_tracker.py summary
python3 scripts/task_tracker.py list --status pending_render
```

---

## 目录结构

```text
yidehai-video/
├── AGENTS.md                              # 项目级总入口（所有桌面 AI 工具通用）：11 形态工作流、合规门禁与迁移指引
├── CLAUDE.md                              # Claude Code 自动引导入口（指向 AGENTS.md）
├── README.md                              # 项目说明文档
├── config.example.json                    # 本地配置结构示例（实际运行配置位于 .yidehai/config.json）
├── .gitignore                             # 忽略 .yidehai/、outputs/* 成片与临时文件
├── assets/
│   └── sfx/                               # [内置·纯离线 CC0] 动效片 5 组 UI 卡点微音效（支持同名 wav/mp3 替换）
├── .yidehai/                              # [自动生成·不入库] 本地配置、密钥、防重账本、任务台账与缓存
├── outputs/                               # [本地产物·不入库] 所有成片 MP4、双封面、审片台与 dashboard.html
│   └── .gitkeep
├── knowledge/
│   ├── 00-auto-setup.md                   # 项目初始化、旧版平滑迁移、OpenMotion / HyperFrames / ego-lite / dreamina 自动安装
│   ├── 01-brand-rules.md                  # 最高优先级：合规禁用词、无浮条利落收尾与统一 EBU R128 音频口径
│   ├── 02-business-faq.md                 # 脱敏版公开业务规则（起收门槛、可收品类、流程口径）
│   ├── 03-copy-formula.md                 # 写稿方法论与四维选题防枯竭矩阵
│   ├── 04-visual-style.md                 # 竖屏安全区、5 套浅色主题轮换、双封面与大字报版式规范
│   ├── 05-good-examples.md                # 已验证过审脚本与大字报样本
│   ├── 06-rendering-playbook.md           # OpenMotion 组件补齐、lint、同步渲染与抽帧质检
│   ├── 07-poster-batch-field-notes.md     # 大字报批量出片实战避坑指南
│   ├── 08-ai-video-engines.md             # 即梦 CLI / Google Flow / 云端视频 API / 实拍混剪 / MotionGit 实操手册
│   ├── 09-motion-batch-field-notes.md     # 动效片批量实战手册（配色轮换 / loudnorm 混音 / 子合成避坑）
│   ├── 10-storybook-workflow.md           # 图文故事片一鱼两吃手册（图源 5 选 1 护栏 + 推镜视频 + 3:4 轮播）
│   ├── 11-local-footage-formats.md        # 本地实拍库专用形态手册（实拍快剪 fastcut & 前后对比片 before_after）
│   └── media-catalog.json                 # 在线免版权 BGM 备用清单（GitHub Releases 托管）
└── scripts/
    ├── setup_project.py                   # 一键项目初始化、旧版平滑迁移、依赖补齐与旧全局 Skill 清理
    ├── media_manager.py                   # 项目本地配置、旧版自动迁移、生成前硬校验、合规校验、防重与在线拉取
    ├── render_poster.py                   # 大字报离线渲染器（关键词高亮 + 逐段轻浮现 + loudnorm + 双封面）
    ├── render_footage_video.py            # 本地素材库离线出片器（实拍快剪 fastcut / 前后对比片 before_after）
    ├── package_ai_video.py                # 通用 AI/实拍视频包装器（HeyGen HyperFrames · loudnorm 混音 · 8 帧质检）
    ├── storybook_builder.py               # 图文故事片构建器（推镜短视频 + 小红书 3:4 轮播套图）
    ├── dreamina_runner.py                 # 即梦 CLI 防呆调度器（提交前原子落盘、防重复扣分、断点续查）
    ├── api_video_runner.py                # 云端视频 API 防呆调度器（5 协议 Adapter · 防重复扣费 · 断点续查）
    ├── api_image_runner.py                # 云端聚合生图调度器（复用 API 余额为图文故事片自动出图）
    ├── batch_runner.py                    # 批量出片调度器（断点续跑 + 可视化审片台 review.html）
    ├── task_tracker.py                    # 跨 Agent 共享任务台账（.yidehai/tasks.json）与离线仪表盘（outputs/dashboard.html）
    ├── motion_templates.py                # 动效片 7 套 MotionFace 风格母版（一卡拆两类/归档/榜单/流程/反转/数字/便签 × 5 浅色主题）
    ├── sfx_manager.py                     # 内置离线 CC0 UI 微音效包生成与按时间轴自动混音器
    ├── fetch_om_components.py             # OpenMotion native 组件镜像补齐与 sha256 校验脚本
    └── link_skill.py                      # [已废弃兼容桩] v2.x 旧指令兼容转发至 setup_project.py
