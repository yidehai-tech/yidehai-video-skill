#!/usr/bin/env python3
"""
亿德海内置离线 CC0 UI 微音效包管理器（纯 Python 标准库 + FFmpeg，零第三方音频库依赖）
--------------------------------------------------------------------------------
内置 5 个温暖、克制、零刺耳感的 Editorial UI 音效（48 kHz 16-bit PCM WAV）：
- whoosh : 轻滑/切卡风声（卡片拆分、条目滑入、大卡抬升）
- pop    : 轻气泡弹出声（卡片出现、标签弹出、榜单条目落位）
- ding   : 温润双音马林巴确认音（✓ 已入袋、正面高亮条）
- tap    : 闷响木质轻敲（红卡「不收」/ VS 胶囊 / 红线划掉提示）
- chime  : 达成和弦印章音（满 5kg/3件盖章、TOP 1 揭示、结尾收口）

若团队成员后续想替换其中任意音色，只需把同名 `<name>.wav` 或 `<name>.mp3` 放进
`assets/sfx/` 即可自动优先生效；删除后仍可随时通过本模块无损重建默认 CC0 音效。
"""

from __future__ import annotations

import argparse
import array
import json
import math
import random
import struct
import subprocess
import sys
import wave
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SFX_DIR = REPO_ROOT / "assets" / "sfx"
BUILTIN_SFX_NAMES = ("whoosh", "pop", "ding", "tap", "chime")
SAMPLE_RATE = 48000


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return lo if v < lo else (hi if v > hi else v)


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge1 <= edge0:
        return 1.0 if x >= edge1 else 0.0
    t = _clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _write_wav_mono(
    path: Path,
    samples: list[float],
    peak: float = 0.84,
    fade_in_ms: float = 3.0,
    fade_out_ms: float = 6.0,
) -> Path:
    """去除直流偏移、施加边缘淡入淡出、归一化峰值并写入 48kHz 16-bit PCM WAV。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    n = len(samples)
    if n == 0:
        raise ValueError(f"Empty sample buffer for {path}")

    mean = sum(samples) / n
    centered = [x - mean for x in samples]

    fade_in_n = min(n // 4, max(1, int(SAMPLE_RATE * fade_in_ms / 1000.0)))
    fade_out_n = min(n // 3, max(1, int(SAMPLE_RATE * fade_out_ms / 1000.0)))
    for i in range(fade_in_n):
        w = 0.5 - 0.5 * math.cos(math.pi * (i + 1) / fade_in_n)
        centered[i] *= w
    for i in range(fade_out_n):
        w = 0.5 - 0.5 * math.cos(math.pi * (i + 1) / fade_out_n)
        centered[n - 1 - i] *= w

    max_abs = max((abs(x) for x in centered), default=0.0)
    scale = (peak / max_abs) if max_abs > 1e-9 else 0.0

    pcm = bytearray(n * 2)
    for i, s in enumerate(centered):
        val = int(round(_clamp(s * scale, -0.999, 0.999) * 32767.0))
        struct.pack_into("<h", pcm, i * 2, val)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(bytes(pcm))
    return path


def _synth_whoosh() -> list[float]:
    """0.28s 丝滑扫风声：SVF 带通噪声扫频 (360 -> 1380 -> 460 Hz) + 柔低频空气感。"""
    dur = 0.28
    n = int(SAMPLE_RATE * dur)
    rng = random.Random(101)
    q = 1.9
    low = 0.0
    band = 0.0
    air_lp = 0.0
    air_alpha = math.exp(-2.0 * math.pi * 180.0 / SAMPLE_RATE)

    out = [0.0] * n
    rise_t = 0.075
    for i in range(n):
        t = i / SAMPLE_RATE
        u = t / dur
        # 平滑钟形扫频曲线
        arch = math.sin(math.pi * u) ** 1.25
        fc = 360.0 + (1380.0 - 360.0) * arch
        # 尾部回落略柔和
        if u > 0.55:
            fc = 460.0 + (fc - 460.0) * (1.0 - _smoothstep(0.55, 1.0, u) * 0.65)

        noise = rng.gauss(0.0, 1.0)
        f = 2.0 * math.sin(math.pi * min(fc, SAMPLE_RATE * 0.22) / SAMPLE_RATE)
        # 2x 过采样步进提高高 Q 状态变量滤波器稳定性
        for _ in range(2):
            high = noise - low - band / q
            band += (f * 0.5) * high
            low += (f * 0.5) * band

        air_lp = air_alpha * air_lp + (1.0 - air_alpha) * noise
        if t < rise_t:
            env = 0.5 - 0.5 * math.cos(math.pi * t / rise_t)
        else:
            env = 0.5 + 0.5 * math.cos(math.pi * (t - rise_t) / (dur - rise_t))
        env = env ** 1.15
        out[i] = env * (band * 0.85 + air_lp * 0.35)
    return out


def _synth_pop() -> list[float]:
    """0.11s 轻气泡弹出声：上行音高正弦滑音 (185 -> 510 Hz) + 柔微瞬态点击。"""
    dur = 0.11
    n = int(SAMPLE_RATE * dur)
    rng = random.Random(202)
    click_low = 0.0
    click_band = 0.0
    click_f = 2.0 * math.sin(math.pi * 1200.0 / SAMPLE_RATE)
    click_q = 2.2

    phase1 = 0.0
    phase2 = 0.0
    out = [0.0] * n
    for i in range(n):
        t = i / SAMPLE_RATE
        glide = 1.0 - math.exp(-t / 0.009) if t < 0.03 else 1.0
        freq = 185.0 + (510.0 - 185.0) * glide
        phase1 += 2.0 * math.pi * freq / SAMPLE_RATE
        phase2 += 2.0 * math.pi * (freq * 2.0) / SAMPLE_RATE

        attack = _smoothstep(0.0, 0.0022, t)
        body_env = attack * math.exp(-t / 0.019)
        harm_env = attack * math.exp(-t / 0.011) * 0.20

        noise = rng.gauss(0.0, 1.0)
        high = noise - click_low - click_band / click_q
        click_band += click_f * high
        click_low += click_f * click_band
        click_env = math.exp(-t / 0.0018) * 0.25 * _smoothstep(0.0, 0.0005, t)

        out[i] = body_env * math.sin(phase1) + harm_env * math.sin(phase2) + click_env * click_band
    return out


def _synth_ding() -> list[float]:
    """0.38s 温润双音玻璃马林巴确认音：C6+C5 -> E6+E5。"""
    dur = 0.38
    n = int(SAMPLE_RATE * dur)
    rng = random.Random(303)
    mallet_lp = 0.0
    mallet_alpha = math.exp(-2.0 * math.pi * 1600.0 / SAMPLE_RATE)

    t2 = 0.045
    out = [0.0] * n
    for i in range(n):
        t = i / SAMPLE_RATE
        # 第一音 C6 (1046.5 Hz) + C5 体音 (-9 dB) + 快速衰减泛音 (-15 dB)
        env1 = _smoothstep(0.0, 0.004, t) * math.exp(-t / 0.110)
        h_env1 = _smoothstep(0.0, 0.003, t) * math.exp(-t / 0.035) * 0.178
        s1 = (
            env1 * (math.sin(2.0 * math.pi * 1046.50 * t) + 0.355 * math.sin(2.0 * math.pi * 523.25 * t))
            + h_env1 * math.sin(2.0 * math.pi * 2093.00 * t)
        )

        # 轻微木槌敲击瞬态 (4ms)
        mallet_lp = mallet_alpha * mallet_lp + (1.0 - mallet_alpha) * rng.gauss(0.0, 1.0)
        mallet_env = math.exp(-t / 0.0016) * 0.18

        # 第二音 E6 (1318.51 Hz, -6 dB) + E5 (-14 dB)
        s2 = 0.0
        if t >= t2:
            dt = t - t2
            env2 = _smoothstep(0.0, 0.004, dt) * math.exp(-dt / 0.115)
            s2 = env2 * (
                0.501 * math.sin(2.0 * math.pi * 1318.51 * dt)
                + 0.200 * math.sin(2.0 * math.pi * 659.25 * dt)
            )

        out[i] = s1 + s2 + mallet_env * mallet_lp
    return out


def _synth_tap() -> list[float]:
    """0.14s 闷响木质轻敲：下行音高木敲 (310 -> 130 Hz) + 轻刷质感。"""
    dur = 0.14
    n = int(SAMPLE_RATE * dur)
    rng = random.Random(404)
    low = 0.0
    band = 0.0
    f = 2.0 * math.sin(math.pi * 900.0 / SAMPLE_RATE)
    q = 2.0

    phase = 0.0
    out = [0.0] * n
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 130.0 + (310.0 - 130.0) * math.exp(-t / 0.008)
        phase += 2.0 * math.pi * freq / SAMPLE_RATE
        knock_env = _smoothstep(0.0, 0.0018, t) * math.exp(-t / 0.020)

        noise = rng.gauss(0.0, 1.0)
        high = noise - low - band / q
        band += f * high
        low += f * band
        brush_env = _smoothstep(0.0, 0.003, t) * math.exp(-t / 0.018) * 0.316

        out[i] = knock_env * math.sin(phase) + brush_env * band
    return out


def _synth_chime() -> list[float]:
    """0.56s 达成和弦印章音：暖低频落槌 + 错拍清润大九和弦 (C5-E5-G5-D6)。"""
    dur = 0.56
    n = int(SAMPLE_RATE * dur)
    notes = (
        (0.000, 523.25, 1.00),
        (0.045, 659.25, 0.85),
        (0.090, 783.99, 0.78),
        (0.138, 1174.66, 0.316),
    )

    thump_phase = 0.0
    out = [0.0] * n
    for i in range(n):
        t = i / SAMPLE_RATE
        # 扎实不刺耳的低频印章底音 (115 -> 75 Hz)
        thump_freq = 75.0 + 40.0 * math.exp(-t / 0.016)
        thump_phase += 2.0 * math.pi * thump_freq / SAMPLE_RATE
        thump = _smoothstep(0.0, 0.003, t) * math.exp(-t / 0.024) * 0.398 * math.sin(thump_phase)

        chord = 0.0
        for onset, freq, amp in notes:
            if t >= onset:
                dt = t - onset
                env = _smoothstep(0.0, 0.006, dt) * math.exp(-dt / 0.160)
                harm = _smoothstep(0.0, 0.005, dt) * math.exp(-dt / 0.055) * 0.126
                chord += amp * (
                    env * math.sin(2.0 * math.pi * freq * dt)
                    + harm * math.sin(4.0 * math.pi * freq * dt)
                )

        out[i] = thump + chord * 0.48
    return out


_SYNTH_BUILDERS = {
    "whoosh": _synth_whoosh,
    "pop": _synth_pop,
    "ding": _synth_ding,
    "tap": _synth_tap,
    "chime": _synth_chime,
}


def generate_builtin_sfx_pack(
    sfx_dir: Path = DEFAULT_SFX_DIR,
    overwrite: bool = False,
) -> dict[str, Path]:
    """生成内置 5 个 CC0 UI 音效到 assets/sfx/（默认不覆盖用户自定义音色）。"""
    sfx_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}
    for name in BUILTIN_SFX_NAMES:
        wav_path = sfx_dir / f"{name}.wav"
        mp3_path = sfx_dir / f"{name}.mp3"
        if not overwrite and (wav_path.exists() or mp3_path.exists()):
            result[name] = wav_path if wav_path.exists() else mp3_path
            continue
        samples = _SYNTH_BUILDERS[name]()
        _write_wav_mono(wav_path, samples)
        result[name] = wav_path
    return result


def resolve_sfx_file(name: str, sfx_dir: Path = DEFAULT_SFX_DIR) -> Path | None:
    """按名称解析音效文件（支持 `<name>.wav` / `<name>.mp3` 用户覆盖，缺失内置音色自动重建）。"""
    clean = str(name or "").strip().lower()
    if not clean:
        return None
    for ext in (".wav", ".mp3"):
        cand = sfx_dir / f"{clean}{ext}"
        if cand.exists() and cand.stat().st_size > 128:
            return cand
    if clean in BUILTIN_SFX_NAMES:
        created = generate_builtin_sfx_pack(sfx_dir, overwrite=False)
        return created.get(clean)
    return None


def load_cues(cues_path: Path) -> list[dict]:
    """安全读取 sfx_cues.json，返回按时间排序的 cue 列表。"""
    if not cues_path.exists():
        return []
    try:
        data = json.loads(cues_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    raw_list = data.get("cues", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    cues: list[dict] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        try:
            t = float(item.get("t", -1.0))
            gain = float(item.get("gain", 0.65))
        except (TypeError, ValueError):
            continue
        sound = str(item.get("sound") or "").strip().lower()
        if sound and t >= 0.0:
            cues.append({
                "t": t,
                "sound": sound,
                "gain": _clamp(gain, 0.05, 1.5),
                "label": str(item.get("label") or sound),
            })
    cues.sort(key=lambda c: c["t"])
    return cues


def _load_stereo_pcm_48k(audio_path: Path, ffmpeg_path: str = "ffmpeg") -> tuple[list[float], list[float]]:
    """读取 48kHz 立体声浮点采样（内置 WAV 纯标准库零子进程直读，自定义 mp3 走单次 FFmpeg 解码）。"""
    if audio_path.suffix.lower() == ".wav":
        try:
            with wave.open(str(audio_path), "rb") as wf:
                ch = wf.getnchannels()
                sw = wf.getsampwidth()
                sr = wf.getframerate()
                if sw == 2 and sr == SAMPLE_RATE and ch in (1, 2):
                    pcm = array.array("h")
                    pcm.frombytes(wf.readframes(wf.getnframes()))
                    if sys.byteorder == "big":
                        pcm.byteswap()
                    inv = 1.0 / 32768.0
                    if ch == 1:
                        mono = [v * inv for v in pcm]
                        return mono, mono
                    left = [pcm[i] * inv for i in range(0, len(pcm), 2)]
                    right = [pcm[i + 1] * inv for i in range(0, len(pcm), 2)]
                    return left, right
        except Exception:
            pass

    proc = subprocess.run(
        [
            ffmpeg_path, "-y", "-v", "error",
            "-i", str(audio_path),
            "-f", "s16le", "-acodec", "pcm_s16le",
            "-ar", str(SAMPLE_RATE), "-ac", "2",
            "pipe:1",
        ],
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        return [], []
    pcm = array.array("h")
    usable = len(proc.stdout) - (len(proc.stdout) % 4)
    pcm.frombytes(proc.stdout[:usable])
    if sys.byteorder == "big":
        pcm.byteswap()
    inv = 1.0 / 32768.0
    left = [pcm[i] * inv for i in range(0, len(pcm), 2)]
    right = [pcm[i + 1] * inv for i in range(0, len(pcm), 2)]
    return left, right


def render_sfx_bed(
    cues: Iterable[dict],
    duration: float,
    out_wav: Path,
    ffmpeg_path: str = "ffmpeg",
    sfx_dir: Path = DEFAULT_SFX_DIR,
) -> int:
    """在纯 Python 中按毫秒采样精度把全部时间轴 cue 合成为等长 48kHz 立体声 WAV（规避多路 amix 挂起），返回有效 cue 数。"""
    dur = max(1.0, float(duration))
    total_samples = int(round(dur * SAMPLE_RATE))
    valid: list[tuple[Path, int, float]] = []
    for c in cues:
        t = float(c.get("t", -1.0))
        if t < 0.0 or t >= dur - 0.03:
            continue
        sfx_file = resolve_sfx_file(str(c.get("sound") or ""), sfx_dir=sfx_dir)
        if sfx_file is None:
            continue
        offset = max(0, int(round(t * SAMPLE_RATE)))
        gain = _clamp(float(c.get("gain", 0.65)), 0.05, 1.5)
        valid.append((sfx_file, offset, gain))

    if not valid:
        return 0

    decoded_cache: dict[Path, tuple[list[float], list[float]]] = {}
    left_buf = [0.0] * total_samples
    right_buf = [0.0] * total_samples
    mixed_count = 0

    for sfx_file, offset, gain in valid:
        if sfx_file not in decoded_cache:
            decoded_cache[sfx_file] = _load_stereo_pcm_48k(sfx_file, ffmpeg_path=ffmpeg_path)
        src_l, src_r = decoded_cache[sfx_file]
        if not src_l:
            continue
        avail = min(len(src_l), total_samples - offset)
        if avail <= 0:
            continue
        for i in range(avail):
            idx = offset + i
            left_buf[idx] += src_l[i] * gain
            right_buf[idx] += src_r[i] * gain
        mixed_count += 1

    if mixed_count == 0:
        return 0

    # 温和软限幅（超出 0.85 时平滑压缩至 <= 0.92，彻底防削波）
    def _soft_limit(x: float) -> int:
        ax = abs(x)
        if ax > 0.85:
            sign = 1.0 if x >= 0.0 else -1.0
            excess = (ax - 0.85) / 0.07
            x = sign * (0.85 + 0.07 * math.tanh(excess))
        return int(round(_clamp(x, -0.92, 0.92) * 32767.0))

    interleaved = array.array("h", [0]) * (total_samples * 2)
    for i in range(total_samples):
        interleaved[i * 2] = _soft_limit(left_buf[i])
        interleaved[i * 2 + 1] = _soft_limit(right_buf[i])
    if sys.byteorder == "big":
        interleaved.byteswap()

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(interleaved.tobytes())
    return mixed_count


def _probe_video_duration(video_path: Path, ffmpeg_path: str) -> float | None:
    ffprobe_bin = str(Path(ffmpeg_path).with_name("ffprobe"))
    if not Path(ffprobe_bin).exists():
        ffprobe_bin = "ffprobe"
    proc = subprocess.run(
        [
            ffprobe_bin, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        val = float(proc.stdout.strip())
        return val if val > 0.2 else None
    except (TypeError, ValueError):
        return None


def mix_preview_video(
    video_path: Path,
    cues_path: Path,
    out_path: Path,
    bgm_path: Path | None = None,
    bgm_start: float = 0.0,
    bgm_vol: float = 0.18,
    sfx_vol: float = 0.55,
    ffmpeg_path: str = "ffmpeg",
    sfx_dir: Path = DEFAULT_SFX_DIR,
) -> dict:
    """将 sfx_cues.json（及可选 BGM）快速混音到已有 MP4 上，用于试听对比。"""
    cues = load_cues(cues_path)
    if not cues:
        raise ValueError(f"No valid cues found in {cues_path}")

    raw_meta = json.loads(cues_path.read_text(encoding="utf-8"))
    meta_dur = float(raw_meta.get("duration", 10.0)) if isinstance(raw_meta, dict) else 10.0
    duration = _probe_video_duration(video_path, ffmpeg_path) or meta_dur
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_sfx = out_path.with_suffix(".sfx_bed.tmp.wav")

    try:
        count = render_sfx_bed(cues, duration, tmp_sfx, ffmpeg_path=ffmpeg_path, sfx_dir=sfx_dir)
        if count == 0:
            raise RuntimeError("Failed to render SFX bed wav")

        fade_out_st = max(0.0, duration - 0.9)
        if bgm_path is not None and bgm_path.exists():
            cmd = [
                ffmpeg_path, "-y", "-v", "error",
                "-i", str(video_path),
                "-stream_loop", "-1", "-ss", f"{bgm_start:.2f}", "-t", f"{duration:.2f}", "-i", str(bgm_path),
                "-i", str(tmp_sfx),
                "-filter_complex",
                f"[1:a]atrim=0:{duration:.2f},asetpts=PTS-STARTPTS,aresample={SAMPLE_RATE},"
                f"loudnorm=I=-16:TP=-2:LRA=11,afade=t=in:st=0:d=0.6,afade=t=out:st={fade_out_st:.2f}:d=0.9,"
                f"volume={bgm_vol:.3f}[b];"
                f"[2:a]aresample={SAMPLE_RATE},volume={sfx_vol:.3f}[s];"
                f"[b][s]amix=inputs=2:normalize=0:duration=longest:dropout_transition=0,alimiter=limit=0.95[a]",
                "-map", "0:v:0", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-t", f"{duration:.2f}", "-movflags", "+faststart",
                str(out_path),
            ]
        else:
            cmd = [
                ffmpeg_path, "-y", "-v", "error",
                "-i", str(video_path),
                "-i", str(tmp_sfx),
                "-filter_complex",
                f"[1:a]aresample={SAMPLE_RATE},volume={sfx_vol:.3f},alimiter=limit=0.95[a]",
                "-map", "0:v:0", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-t", f"{duration:.2f}", "-movflags", "+faststart",
                str(out_path),
            ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not out_path.exists():
            raise RuntimeError(f"FFmpeg mix failed: {(proc.stderr or proc.stdout).strip()}")
        return {"out": str(out_path), "cues": count, "duration": round(duration, 3), "bgm": str(bgm_path) if bgm_path else "none"}
    finally:
        tmp_sfx.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="亿德海内置离线 CC0 UI 微音效包生成与混音工具")
    parser.add_argument("--generate", action="store_true", help="生成 5 个内置 CC0 WAV 音效到 assets/sfx/")
    parser.add_argument("--overwrite", action="store_true", help="与 --generate 配合，覆盖已有同名 WAV")
    parser.add_argument("--sfx-dir", type=Path, default=DEFAULT_SFX_DIR, help="音效目录（默认 assets/sfx/）")
    parser.add_argument("--mix-preview", action="store_true", help="按 sfx_cues.json 为现有 MP4 混入 SFX（及可选 BGM）")
    parser.add_argument("--video", type=Path, help="输入无声或原版 MP4")
    parser.add_argument("--cues", type=Path, help="sfx_cues.json 路径")
    parser.add_argument("--out", type=Path, help="输出 MP4 路径")
    parser.add_argument("--bgm", type=Path, default=None, help="可选 BGM 文件路径")
    parser.add_argument("--bgm-start", type=float, default=0.0, help="BGM 起始偏移秒数")
    parser.add_argument("--bgm-vol", type=float, default=0.18, help="BGM 混音音量系数（默认 0.18）")
    parser.add_argument("--sfx-vol", type=float, default=0.55, help="SFX 混音音量系数（默认 0.55）")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg 可执行文件路径")
    args = parser.parse_args()

    if args.generate:
        files = generate_builtin_sfx_pack(sfx_dir=args.sfx_dir, overwrite=args.overwrite)
        print(json.dumps({k: str(v) for k, v in files.items()}, ensure_ascii=False, indent=2))
        return 0

    if args.mix_preview:
        if not args.video or not args.cues or not args.out:
            parser.error("--mix-preview requires --video, --cues, and --out")
        res = mix_preview_video(
            video_path=args.video,
            cues_path=args.cues,
            out_path=args.out,
            bgm_path=args.bgm,
            bgm_start=args.bgm_start,
            bgm_vol=args.bgm_vol,
            sfx_vol=args.sfx_vol,
            ffmpeg_path=args.ffmpeg,
            sfx_dir=args.sfx_dir,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
