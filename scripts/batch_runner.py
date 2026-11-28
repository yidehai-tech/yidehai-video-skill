#!/usr/bin/env python3
"""
亿德海团队短视频批量工厂调度器（跨平台 macOS / Windows）
支持多形态混合批量出片、默认 50%「大字报」+ 50%「动效片」、合规硬拦截、全局防重、断点续跑与可视化审片页。

支持的中文/英文形态映射：
- 大字报（poster / dazibao）：调用内置 render_poster.py，8.8s 一镜到底满屏大字，9 秒出片
- 动效片（motion / openmotion / 动效视频）：自动检测本机 OpenMotion/HyperFrames 前台同步渲染；若引擎未就绪则优雅标记待渲并输出工程规范，绝不阻塞整批任务或拼凑低质占位片
"""

import argparse
import concurrent.futures
import hashlib
import html
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = PROJECT_ROOT
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import media_manager
import motion_templates
import render_poster
import sfx_manager
import task_tracker

TYPE_ALIASES = {
    "大字报": "poster",
    "大字报视频": "poster",
    "poster": "poster",
    "dazibao": "poster",
    "动效片": "motion",
    "动效视频": "motion",
    "动态卡片": "motion",
    "motion": "motion",
    "openmotion": "motion",
}

TYPE_DISPLAY = {
    "poster": "大字报",
    "motion": "动效片",
}

FORBIDDEN_TERMS = media_manager.FORBIDDEN_TERMS


def normalize_type(raw: str) -> str:
    key = (raw or "poster").strip().lower()
    if key in TYPE_ALIASES:
        return TYPE_ALIASES[key]
    raise ValueError(f"不支持的视频类型：{raw}（支持：大字报 / 动效片）")


def check_compliance(item: dict) -> list[str]:
    chunks = [
        str(item.get("title", "")),
        "\n".join(item["body"]) if isinstance(item.get("body"), list) else str(item.get("body", "")),
        str(item.get("question", "")),
        str(item.get("pill", "")),
        str(item.get("publish_copy", "")),
        str(item.get("voiceover_text", "")),
    ]
    return media_manager.check_forbidden_terms(chunks)


def item_copy_hash(item: dict) -> str:
    title = str(item.get("title", "")).strip()
    body = item.get("body", "")
    body_str = "\n".join(body) if isinstance(body, list) else str(body)
    return hashlib.sha256((title + "\n" + body_str.strip()).encode("utf-8")).hexdigest()[:16]


def detect_openmotion_runtime() -> dict | None:
    """自动检测本机已安装且导出就绪的 OpenMotion / HyperFrames 渲染环境（不写死路径/版本）。"""
    candidates = []
    if os.environ.get("OPENMOTION_HOME"):
        candidates.append(Path(os.environ["OPENMOTION_HOME"]))
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]) / "openmotion")
    candidates.extend([
        Path.home() / ".openmotion",
        Path.home() / "Library" / "Application Support" / "openmotion",
        Path.home() / ".local" / "share" / "openmotion",
    ])

    for om_home in candidates:
        install_json = om_home / "install.json"
        if not install_json.exists():
            continue
        try:
            meta = json.loads(install_json.read_text(encoding="utf-8"))
            app_root = Path(meta.get("appRoot", ""))
            hf_bin = app_root / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
            lock_file = app_root / "scripts" / "runtime-lock.json"
            if not hf_bin.exists() or not lock_file.exists():
                continue
            lock = json.loads(lock_file.read_text(encoding="utf-8"))
            cache_dir = om_home / "cache" / "native"
            target_key = "win-x64" if sys.platform.startswith("win") else ("mac-arm64" if os.uname().machine == "arm64" else "mac-x64")
            tinfo = lock.get("targets", {}).get(target_key, {})
            browser_info = tinfo.get("browser", {})
            media_info = tinfo.get("media", {})
            b_sha = browser_info.get("sha256", "")
            m_sha = media_info.get("sha256", "")
            b_exec = cache_dir / target_key / f"browser-{b_sha}" / browser_info.get("executable", "")
            m_dir = cache_dir / target_key / f"media-{m_sha}" / media_info.get("directory", "")
            ffmpeg_bin = m_dir / "bin" / ("ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg")
            ffprobe_bin = m_dir / "bin" / ("ffprobe.exe" if sys.platform.startswith("win") else "ffprobe")
            if b_exec.exists() and ffmpeg_bin.exists() and ffprobe_bin.exists():
                return {
                    "om_home": str(om_home),
                    "app_root": str(app_root),
                    "hf_bin": str(hf_bin),
                    "browser_path": str(b_exec),
                    "ffmpeg_path": str(ffmpeg_bin),
                    "ffprobe_path": str(ffprobe_bin),
                }
        except Exception:
            continue
    return None


def build_motion_html_project(item: dict, proj_dir: Path, idx: int = 0) -> str:
    """调用 7 套 MotionFace 风格高质感动效片母版（split_compare / pack_archive / ranking / step_flow / myth_flip / metric_spotlight / prep_memo）生成工程。"""
    return motion_templates.build_motion_project(item, proj_dir, fallback_index=idx)


def run_one_item(
    item: dict,
    out_root: Path,
    om_runtime: dict | None,
    silent_default: bool,
    bg_dir_override: str | None,
    bgm_dir_override: str | None,
    preassigned_bg: tuple[Path, float] | None = None,
) -> dict:
    item_id = item["id"]
    norm_type = normalize_type(item.get("type", "大字报"))
    type_zh = TYPE_DISPLAY[norm_type]
    item_dir = out_root / f"{item_id}-{type_zh}"
    item_dir.mkdir(parents=True, exist_ok=True)
    job_path = item_dir / "job.json"
    job_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")

    if norm_type == "poster":
        cmd = [
            sys.executable, str(SCRIPTS_DIR / "render_poster.py"),
            "--job", str(job_path),
            "--out-dir", str(item_dir),
            "--force",
        ]
        if preassigned_bg is not None:
            cmd += ["--bg", str(preassigned_bg[0]), "--bg-start", f"{preassigned_bg[1]:.2f}"]
        elif bg_dir_override:
            cmd += ["--bg-dir", bg_dir_override]
        if bgm_dir_override:
            cmd += ["--bgm-dir", bgm_dir_override]
        if item.get("silent", silent_default):
            cmd.append("--silent")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            return {"id": item_id, "type": "poster", "status": "failed", "error": (proc.stderr or proc.stdout).strip()[-400:]}
        res = json.loads(proc.stdout.strip().splitlines()[-1] if proc.stdout.strip().startswith("{") is False else proc.stdout)
        return {
            "id": item_id,
            "type": "poster",
            "type_zh": TYPE_DISPLAY["poster"],
            "title": item.get("title", ""),
            "status": "done",
            "mp4": res["mp4"],
            "cover_9x16": res["cover_9x16"],
            "cover_3x4": res["cover_3x4"],
            "duration": res.get("duration"),
            "bg": res.get("bg"),
            "bgm": res.get("bgm"),
        }

    # 动效片（motion）：走三套高转化母版轮换 + OpenMotion / HyperFrames 前台同步渲染
    proj_dir = item_dir / "motion-project"
    style_idx = int(re.sub(r"\D", "", item_id) or "0")
    chosen_style = build_motion_html_project(item, proj_dir, idx=style_idx)
    if om_runtime is None:
        note_msg = f"已按高转化母版 [{chosen_style}] 生成规范动效工程；本机 OpenMotion 导出组件就绪后重跑本命令即可自动续渲。"
        task_tracker.safe_record_task(
            track="motion",
            title=str(item.get("title", "")).replace("\n", " "),
            status="pending_render",
            slug=str(item.get("slug", item_id)),
            out_dir=str(item_dir),
            note=note_msg,
            copy_text=str(item.get("publish_copy") or ""),
        )
        return {
            "id": item_id,
            "type": "motion",
            "type_zh": TYPE_DISPLAY["motion"],
            "motion_style": chosen_style,
            "title": item.get("title", ""),
            "status": "pending_motion_engine",
            "project_dir": str(proj_dir),
            "note": note_msg,
        }

    motion_task_id = task_tracker.safe_start_task(
        track="motion",
        title=str(item.get("title", "")).replace("\n", " "),
        slug=str(item.get("slug", item_id)),
        out_dir=str(item_dir),
        copy_text=str(item.get("publish_copy") or ""),
    )

    out_mp4 = item_dir / f"{item.get('slug', item_id)}.mp4"
    env = os.environ.copy()
    env["HYPERFRAMES_FFMPEG_PATH"] = om_runtime["ffmpeg_path"]
    env["HYPERFRAMES_FFPROBE_PATH"] = om_runtime["ffprobe_path"]
    env["HYPERFRAMES_BROWSER_PATH"] = om_runtime["browser_path"]
    env["HYPERFRAMES_TELEMETRY_DISABLED"] = "1"

    cmd = ["node", om_runtime["hf_bin"], "render", "-o", str(out_mp4), str(proj_dir)]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0 or not out_mp4.exists():
        err_msg = (proc.stderr or proc.stdout).strip()[-400:]
        task_tracker.safe_finish_task(motion_task_id, status="failed", error=err_msg)
        return {"id": item_id, "type": "motion", "type_zh": TYPE_DISPLAY["motion"], "title": item.get("title", ""), "status": "failed", "error": err_msg}

    # 默认给动效片合成「中文 AI 旁白（Edge-TTS）+ 12% 真实无版权 BGM」有声版，并保留同配色无声版；
    # 仅成员明确要求 --silent 或确无真实音源时回落无声版，并在结果里写明原因。
    bgm_label = "silent"
    voice_label = "none"
    sfx_label = "off"
    slug_name = item.get("slug", item_id)
    silent_mp4 = item_dir / f"{slug_name}-无声版.mp4"
    if not item.get("silent", silent_default):
        shutil.copy2(out_mp4, silent_mp4)
        cfg = media_manager.load_config()
        ledger_path = Path(cfg["ledger_path"])
        ledger = render_poster.load_ledger(ledger_path)
        duration = max(3.0, float(item.get("duration", 10.0)))

        # 0) 合成内置离线 CC0 UI 微音效卡点音轨（可通过 item["sfx"]=False 关闭）
        sfx_enabled = bool(item.get("sfx", True))
        sfx_bed_wav = item_dir / "_sfx_bed.wav"
        sfx_cue_count = 0
        cues_file = proj_dir / "sfx_cues.json"
        if sfx_enabled and cues_file.exists():
            sfx_cues = sfx_manager.load_cues(cues_file)
            if sfx_cues:
                sfx_cue_count = sfx_manager.render_sfx_bed(
                    sfx_cues,
                    duration,
                    sfx_bed_wav,
                    ffmpeg_path=om_runtime["ffmpeg_path"],
                )
        if sfx_cue_count > 0:
            sfx_label = f"built-in({sfx_cue_count} cues)"

        # 1) 可选合成中文旁白（优先用 voiceover_text，否则取标题+正文前 55 字）
        vo_text = str(item.get("voiceover_text") or "").strip()
        if not vo_text:
            body_raw = item.get("body", [])
            body_str = "".join(body_raw) if isinstance(body_raw, list) else str(body_raw)
            vo_text = (str(item.get("title", "")).replace("\n", "，") + "。" + body_str.replace("\n", "")).strip()[:55]
        voice_mp3 = item_dir / "_voice.mp3"
        has_voice = False
        if vo_text:
            edge_bin = shutil.which("edge-tts") or shutil.which("edge-tts.exe")
            tts_cmd = (
                [edge_bin, "--voice", "zh-CN-XiaoxiaoNeural", "--rate=+10%", "--text", vo_text, "--write-media", str(voice_mp3)]
                if edge_bin else
                [sys.executable, "-m", "edge_tts", "--voice", "zh-CN-XiaoxiaoNeural", "--rate=+10%", "--text", vo_text, "--write-media", str(voice_mp3)]
            )
            tts_proc = subprocess.run(tts_cmd, capture_output=True, text=True)
            if tts_proc.returncode == 0 and voice_mp3.exists() and voice_mp3.stat().st_size > 1000:
                has_voice = True
                voice_label = "zh-CN-XiaoxiaoNeural"

        # 2) 抽取真实无版权 BGM（12% 音量）
        bgm_dirs = [Path(bgm_dir_override)] if bgm_dir_override else (
            [Path(cfg["cache_bgm_dir"])] + [Path(d) for d in cfg.get("local_bgm_dirs", [])]
        )
        picked_bgm = render_poster.pick_unique_bgm(bgm_dirs, duration, ledger)
        if picked_bgm is None:
            media_manager.ensure_online_media("bgm_tracks", count=2, cfg=cfg)
            picked_bgm = render_poster.pick_unique_bgm([Path(cfg["cache_bgm_dir"])], duration, ledger)

        muxed_mp4 = item_dir / f"{slug_name}.muxed.mp4"
        fade_out_st = max(0.0, duration - 0.9)
        mux_ok = False
        audio_note = ""

        def _probe_voice_tempo() -> float:
            vp = subprocess.run([
                om_runtime["ffprobe_path"], "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(voice_mp3),
            ], capture_output=True, text=True)
            try:
                v_dur = float(vp.stdout.strip())
            except Exception:
                v_dur = max(1.0, duration - 0.6)
            return min(1.5, max(1.0, v_dur / max(1.0, duration - 0.6)))

        if has_voice and picked_bgm is not None:
            bgm_src, bgm_start = picked_bgm
            tempo = _probe_voice_tempo()
            mux_cmd = [
                om_runtime["ffmpeg_path"], "-y", "-v", "error",
                "-i", str(out_mp4),
                "-i", str(voice_mp3),
                "-stream_loop", "-1", "-ss", f"{bgm_start:.2f}", "-t", f"{duration:.2f}", "-i", str(bgm_src),
            ]
            fc = (
                f"[1:a]aresample=48000,atempo={tempo:.3f},loudnorm=I=-14:TP=-1.5:LRA=7,apad,atrim=0:{max(1.0, duration-0.4):.2f}[v];"
                f"[2:a]atrim=0:{duration:.2f},asetpts=PTS-STARTPTS,aresample=48000,loudnorm=I=-16:TP=-2:LRA=11,afade=t=in:st=0:d=0.6,afade=t=out:st={fade_out_st:.2f}:d=0.9,volume=0.18[b];"
            )
            if sfx_cue_count > 0:
                mux_cmd.extend(["-i", str(sfx_bed_wav)])
                fc += (
                    f"[3:a]aresample=48000,volume=0.38[s];"
                    f"[v][b][s]amix=inputs=3:normalize=0:duration=longest:dropout_transition=0,alimiter=limit=0.95[a]"
                )
            else:
                fc += "[v][b]amix=inputs=2:normalize=0:duration=longest:dropout_transition=0,alimiter=limit=0.95[a]"
            mux_cmd.extend([
                "-filter_complex", fc,
                "-map", "0:v:0", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-t", f"{duration:.2f}", "-movflags", "+faststart",
                str(muxed_mp4),
            ])
            mux_proc = subprocess.run(mux_cmd, capture_output=True, text=True)
            if mux_proc.returncode == 0 and muxed_mp4.exists():
                muxed_mp4.replace(out_mp4)
                render_poster.save_ledger(ledger_path, ledger)
                sfx_tag = "+sfx" if sfx_cue_count > 0 else ""
                bgm_label = f"{bgm_src.name}@{bgm_start:.1f}s(loudnorm+18%{sfx_tag})"
                mux_ok = True
            else:
                audio_note = f"旁白+BGM 混音失败：{(mux_proc.stderr or '')[-200:]}"
        elif has_voice:
            # 补齐「仅旁白」分支：无 BGM 时绝不丢弃已生成的中文旁白
            tempo = _probe_voice_tempo()
            mux_cmd = [
                om_runtime["ffmpeg_path"], "-y", "-v", "error",
                "-i", str(out_mp4),
                "-i", str(voice_mp3),
            ]
            if sfx_cue_count > 0:
                mux_cmd.extend(["-i", str(sfx_bed_wav)])
                fc = (
                    f"[1:a]aresample=48000,atempo={tempo:.3f},loudnorm=I=-14:TP=-1.5:LRA=7,apad,atrim=0:{max(1.0, duration-0.4):.2f}[v];"
                    f"[2:a]aresample=48000,volume=0.38[s];"
                    f"[v][s]amix=inputs=2:normalize=0:duration=longest:dropout_transition=0,alimiter=limit=0.95[a]"
                )
            else:
                fc = f"[1:a]aresample=48000,atempo={tempo:.3f},loudnorm=I=-14:TP=-1.5:LRA=7,apad,atrim=0:{duration:.2f},alimiter=limit=0.95[a]"
            mux_cmd.extend([
                "-filter_complex", fc,
                "-map", "0:v:0", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-t", f"{duration:.2f}", "-movflags", "+faststart",
                str(muxed_mp4),
            ])
            mux_proc = subprocess.run(mux_cmd, capture_output=True, text=True)
            if mux_proc.returncode == 0 and muxed_mp4.exists():
                muxed_mp4.replace(out_mp4)
                bgm_label = "voice+sfx-no-bgm" if sfx_cue_count > 0 else "voice-only-no-bgm-source"
                audio_note = "本机未找到真实 BGM，已保留中文旁白" + ("+内置卡点音效（无背景音乐）。" if sfx_cue_count > 0 else "（无背景音乐）。")
                mux_ok = True
            else:
                audio_note = f"纯旁白混音失败：{(mux_proc.stderr or '')[-200:]}"
        elif picked_bgm is not None:
            bgm_src, bgm_start = picked_bgm
            mux_cmd = [
                om_runtime["ffmpeg_path"], "-y", "-v", "error",
                "-i", str(out_mp4),
                "-stream_loop", "-1", "-ss", f"{bgm_start:.2f}", "-t", f"{duration:.2f}", "-i", str(bgm_src),
            ]
            fc = (
                f"[1:a]atrim=0:{duration:.2f},asetpts=PTS-STARTPTS,aresample=48000,"
                f"loudnorm=I=-16:TP=-2:LRA=11,afade=t=in:st=0:d=0.6,afade=t=out:st={fade_out_st:.2f}:d=0.9,volume=0.18[b];"
            )
            if sfx_cue_count > 0:
                mux_cmd.extend(["-i", str(sfx_bed_wav)])
                fc += (
                    f"[2:a]aresample=48000,volume=0.52[s];"
                    f"[b][s]amix=inputs=2:normalize=0:duration=longest:dropout_transition=0,alimiter=limit=0.95[a]"
                )
            else:
                fc += "[b]alimiter=limit=0.95[a]"
            mux_cmd.extend([
                "-filter_complex", fc,
                "-map", "0:v:0", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-t", f"{duration:.2f}", "-movflags", "+faststart",
                str(muxed_mp4),
            ])
            mux_proc = subprocess.run(mux_cmd, capture_output=True, text=True)
            if mux_proc.returncode == 0 and muxed_mp4.exists():
                muxed_mp4.replace(out_mp4)
                render_poster.save_ledger(ledger_path, ledger)
                sfx_tag = "+sfx" if sfx_cue_count > 0 else ""
                bgm_label = f"{bgm_src.name}@{bgm_start:.1f}s(loudnorm+18%{sfx_tag})"
                audio_note = "edge-tts 未就绪，本次混入真实无版权 BGM" + ("+内置卡点音效（无旁白）。" if sfx_cue_count > 0 else "（无旁白）。")
                mux_ok = True
            else:
                audio_note = f"BGM 混音失败：{(mux_proc.stderr or '')[-200:]}"
        elif sfx_cue_count > 0:
            mux_proc = subprocess.run([
                om_runtime["ffmpeg_path"], "-y", "-v", "error",
                "-i", str(out_mp4),
                "-i", str(sfx_bed_wav),
                "-filter_complex",
                f"[1:a]aresample=48000,volume=0.60,alimiter=limit=0.95[a]",
                "-map", "0:v:0", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-t", f"{duration:.2f}", "-movflags", "+faststart",
                str(muxed_mp4),
            ], capture_output=True, text=True)
            if mux_proc.returncode == 0 and muxed_mp4.exists():
                muxed_mp4.replace(out_mp4)
                bgm_label = "sfx-only-no-voice-bgm"
                audio_note = "未检测到 edge-tts 且无真实 BGM 源，仅混入内置离线卡点音效。"
                mux_ok = True
            else:
                audio_note = f"纯音效混音失败：{(mux_proc.stderr or '')[-200:]}"
        else:
            bgm_label = "silent-no-audio-source"
            audio_note = "未检测到 edge-tts 且无真实 BGM 源，回落为无声版。"
        voice_mp3.unlink(missing_ok=True)
        sfx_bed_wav.unlink(missing_ok=True)

        # 用 ffprobe 验证最终文件确实含音轨，按真实交付完整度标记 done / degraded / failed
        ap = subprocess.run([
            om_runtime["ffprobe_path"], "-v", "error", "-select_streams", "a",
            "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(out_mp4),
        ], capture_output=True, text=True)
        has_final_audio = bool(ap.stdout.strip())
        if not has_final_audio:
            voice_label = "none"
            if bgm_label not in ("silent", "silent-no-audio-source"):
                bgm_label = "mux-failed"
        if mux_ok and has_final_audio and has_voice and picked_bgm is not None:
            final_status = "done"
        elif has_final_audio:
            # 仅旁白缺 BGM 或仅 BGM 缺旁白：标为 degraded，允许补齐音源后续跑重混
            final_status = "degraded"
        else:
            final_status = "degraded" if bgm_label == "silent-no-audio-source" else "failed"
    else:
        audio_note = "按要求输出无声版。"
        final_status = "done"

    cover_9x16 = item_dir / "cover-9x16.jpg"
    cover_3x4 = item_dir / "cover-3x4.jpg"
    subprocess.run([om_runtime["ffmpeg_path"], "-y", "-v", "error", "-ss", "1.0", "-i", str(out_mp4), "-frames:v", "1", "-q:v", "2", str(cover_9x16)], check=False)
    if cover_9x16.exists():
        subprocess.run([om_runtime["ffmpeg_path"], "-y", "-v", "error", "-i", str(cover_9x16), "-vf", "crop=1080:1440:0:180", "-q:v", "2", str(cover_3x4)], check=False)

    task_tracker.safe_finish_task(
        motion_task_id,
        status="done" if final_status in ("done", "degraded") else "failed",
        video=str(out_mp4),
        cover_9x16=str(cover_9x16) if cover_9x16.exists() else "",
        cover_3x4=str(cover_3x4) if cover_3x4.exists() else "",
        duration_sec=float(item.get("duration", 10.0)),
        bgm=bgm_label,
        note=(f"[degraded] {audio_note}" if final_status == "degraded" else audio_note),
        error=(audio_note if final_status == "failed" else ""),
    )

    return {
        "id": item_id,
        "type": "motion",
        "type_zh": TYPE_DISPLAY["motion"],
        "motion_style": chosen_style,
        "title": item.get("title", ""),
        "status": final_status,
        "mp4": str(out_mp4),
        "silent_mp4": str(silent_mp4) if silent_mp4.exists() else "",
        "voice": voice_label,
        "bgm": bgm_label,
        "sfx": sfx_label,
        "audio_note": audio_note,
        "cover_9x16": str(cover_9x16) if cover_9x16.exists() else "",
        "cover_3x4": str(cover_3x4) if cover_3x4.exists() else "",
    }


def write_review_html(out_root: Path, results: list[dict]) -> Path:
    cards = []
    for r in results:
        rel_mp4 = os.path.relpath(r["mp4"], out_root) if r.get("mp4") else ""
        rel_cov = os.path.relpath(r["cover_9x16"], out_root) if r.get("cover_9x16") else ""
        badge = html.escape(r.get("type_zh", r.get("type", "")))
        status = html.escape(r.get("status", ""))
        title = html.escape(str(r.get("title", "")).replace("\n", " "))
        media_html = (
            f'<video controls preload="none" poster="{html.escape(rel_cov)}" src="{html.escape(rel_mp4)}"></video>'
            if rel_mp4 else f'<div class="placeholder">{html.escape(r.get("note") or r.get("error") or status)}</div>'
        )
        note_text = str(r.get("audio_note") or r.get("note") or r.get("error") or "").strip()
        note_html = f'<div class="note">{html.escape(note_text)}</div>' if note_text else ""
        cards.append(f"""
        <div class="card" data-type="{html.escape(r.get('type',''))}" data-status="{status}">
          <div class="meta"><span class="tag">{badge}</span><span class="st {status}">{status}</span><span class="cid">{html.escape(r['id'])}</span></div>
          {media_html}
          <div class="title">{title}</div>
          {note_html}
        </div>""")

    page = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>亿德海批量审片台</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; background: #0f1412; color: #f1f5f3; margin: 0; padding: 24px; }}
  h1 {{ margin: 0 0 12px; font-size: 22px; }}
  .bar {{ display: flex; gap: 10px; margin-bottom: 18px; flex-wrap: wrap; }}
  button {{ background: #1e2d27; color: #fff; border: 1px solid #355246; padding: 8px 14px; border-radius: 8px; cursor: pointer; }}
  button.active {{ background: #2f9e44; border-color: #2f9e44; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }}
  .card {{ background: #17201c; border: 1px solid #263830; border-radius: 12px; padding: 12px; display: flex; flex-direction: column; gap: 8px; }}
  .meta {{ display: flex; gap: 6px; align-items: center; font-size: 12px; }}
  .tag {{ background: #264d3b; padding: 2px 8px; border-radius: 999px; }}
  .st.done {{ color: #69db7c; }} .st.degraded {{ color: #ffa94d; }} .st.pending_motion_engine {{ color: #ffd43b; }} .st.failed {{ color: #ff6b6b; }}
  .note {{ font-size: 12px; color: #ffa94d; line-height: 1.4; }}
  .cid {{ margin-left: auto; color: #8fa399; }}
  video {{ width: 100%; aspect-ratio: 9/16; background: #000; border-radius: 8px; }}
  .placeholder {{ width: 100%; aspect-ratio: 9/16; background: #111815; border-radius: 8px; display: flex; align-items: center; justify-content: center; padding: 16px; text-align: center; font-size: 13px; color: #ffd43b; box-sizing: border-box; }}
  .title {{ font-size: 13px; line-height: 1.4; color: #dce6e0; }}
</style></head><body>
<h1>亿德海批量短视频审片台（共 {len(results)} 条）</h1>
<div class="bar">
  <button class="active" onclick="flt('all',this)">全部</button>
  <button onclick="flt('poster',this)">大字报</button>
  <button onclick="flt('motion',this)">动效片</button>
</div>
<div class="grid">{''.join(cards)}</div>
<script>
function flt(t, btn) {{
  document.querySelectorAll('.bar button').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.card').forEach(c=>{{
    c.style.display = (t==='all' || c.dataset.type===t) ? 'flex' : 'none';
  }});
}}
</script></body></html>"""
    review_path = out_root / "review.html"
    review_path.write_text(page, encoding="utf-8")
    return review_path


def main() -> None:
    parser = argparse.ArgumentParser(description="亿德海批量短视频工厂（默认 50% 大字报 + 50% 动效片，支持断点续跑）")
    parser.add_argument("--manifest", required=True, help="批量任务 JSON（items 列表，每项可填 type: 大字报 / 动效片）")
    parser.add_argument("--out-dir", required=True, help="本批输出根目录")
    parser.add_argument("--organize-by-date", action="store_true", help="自动按 YYYY-MM-DD/batch-<清单8位哈希>/ 归档（支持同清单断点续跑）")
    parser.add_argument("--workers", type=int, default=1, help="大字报并发渲染线程数（默认 1 串行最稳；父进程已预分配防重背景）")
    parser.add_argument("--silent", action="store_true", help="整批默认导出无声版")
    parser.add_argument("--bg-dir", help="可选覆盖背景空镜目录")
    parser.add_argument("--bgm-dir", help="可选覆盖 BGM 目录")
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    items = manifest if isinstance(manifest, list) else manifest.get("items", [])
    if not items:
        raise ValueError("manifest 中没有 items 条目")

    # 1. 全批合规硬拦截 + ID 唯一性校验 + 批内查重 + 默认 50/50 类型分配
    seen_hashes = set()
    seen_ids = set()
    compliance_errors = []
    for idx, it in enumerate(items):
        raw_id = it.get("id") or f"V{idx+1:03d}"
        safe_id = media_manager.sanitize_slug(raw_id, fallback=f"V{idx+1:03d}")
        if safe_id.lower() in seen_ids:
            compliance_errors.append(f"条目 ID 重复（忽略大小写）：{safe_id}")
        seen_ids.add(safe_id.lower())
        it["id"] = safe_id
        if not it.get("type"):
            it["type"] = "大字报" if idx % 2 == 0 else "动效片"
        it["slug"] = media_manager.sanitize_slug(it.get("slug") or safe_id.lower(), fallback=safe_id.lower())
        hits = check_compliance(it)
        if hits:
            compliance_errors.append(f"{it['id']} 命中红线词：{', '.join(hits)}")
        h = item_copy_hash(it)
        if h in seen_hashes:
            compliance_errors.append(f"{it['id']} 与本批前文文案完全重复")
        seen_hashes.add(h)

    if compliance_errors:
        print(json.dumps({"ok": False, "stage": "precheck", "errors": compliance_errors}, ensure_ascii=False, indent=2))
        sys.exit(2)

    now = datetime.now()
    manifest_sha8 = hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest()[:8]
    out_root = Path(args.out_dir)
    if args.organize_by_date:
        out_root = out_root / now.strftime("%Y-%m-%d") / f"batch-{manifest_sha8}"
    out_root.mkdir(parents=True, exist_ok=True)
    progress_path = out_root / "progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {}

    # 2. 预检 OpenMotion 动效片引擎（不阻塞大字报渲染）
    need_motion = any(normalize_type(it["type"]) == "motion" for it in items)
    om_runtime = detect_openmotion_runtime() if need_motion else None

    # 3. 断点续跑：拆分待跑项
    todo_poster = []
    todo_motion = []
    batch_used_bg_files: set[str] = set()
    for prev in progress.values():
        if prev.get("status") == "done" and prev.get("bg") and "@" in str(prev["bg"]):
            batch_used_bg_files.add(str(prev["bg"]).split("@", 1)[0])

    for it in items:
        prev = progress.get(it["id"])
        if prev and prev.get("status") == "done" and prev.get("mp4") and Path(prev["mp4"]).exists():
            continue
        if normalize_type(it["type"]) == "poster":
            todo_poster.append(it)
        else:
            todo_motion.append(it)

    # 4. 父进程统一为大字报预分配「不同视频文件优先」的不重复背景，彻底消除并发读写账本竞态
    preassigned_map: dict[str, tuple[Path, float] | None] = {}
    if todo_poster:
        cfg = media_manager.load_config()
        ledger_path = Path(cfg["ledger_path"])
        ledger = render_poster.load_ledger(ledger_path)
        bg_dirs: list[Path] = []
        if args.bg_dir:
            bg_dirs.append(Path(args.bg_dir))
        else:
            bg_src = cfg.get("bg_source", "both")
            if bg_src in ("both", "local"):
                bg_dirs.extend(Path(d) for d in cfg.get("local_bg_dirs", []))
            if bg_src in ("both", "online"):
                bg_dirs.append(Path(cfg["cache_bgm_dir"].replace("/bgm", "/bg")) if False else Path(cfg["cache_bg_dir"]))

        for it in todo_poster:
            dur = float(it.get("duration", 8.8))
            picked = render_poster.pick_unique_bg_segment(bg_dirs, dur, ledger, exclude_files=batch_used_bg_files)
            if picked is not None:
                batch_used_bg_files.add(picked[0].name)
            preassigned_map[it["id"]] = picked
        render_poster.save_ledger(ledger_path, ledger)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
            futs = [
                ex.submit(
                    run_one_item, it, out_root, None, args.silent,
                    args.bg_dir, args.bgm_dir, preassigned_map.get(it["id"]),
                )
                for it in todo_poster
            ]
            for fut in concurrent.futures.as_completed(futs):
                res = fut.result()
                progress[res["id"]] = res
                media_manager.atomic_write_json(progress_path, progress)

    for it in todo_motion:
        res = run_one_item(it, out_root, om_runtime, args.silent, args.bg_dir, args.bgm_dir)
        progress[res["id"]] = res
        media_manager.atomic_write_json(progress_path, progress)

    ordered = [progress[it["id"]] for it in items if it["id"] in progress]
    review_html = write_review_html(out_root, ordered)

    failed_cnt = sum(1 for r in ordered if r["status"] == "failed")
    degraded_cnt = sum(1 for r in ordered if r["status"] == "degraded")
    pending_cnt = sum(1 for r in ordered if r["status"] == "pending_motion_engine")
    summary = {
        "ok": failed_cnt == 0 and degraded_cnt == 0 and pending_cnt == 0,
        "total": len(ordered),
        "done": sum(1 for r in ordered if r["status"] == "done"),
        "degraded": degraded_cnt,
        "pending_motion_engine": pending_cnt,
        "failed": failed_cnt,
        "review_html": str(review_html),
        "progress_json": str(progress_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
