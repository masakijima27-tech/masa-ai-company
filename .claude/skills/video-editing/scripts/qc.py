#!/usr/bin/env python3
"""品質改札。final.mp4 を出荷前に自動チェックし、NGなら非ゼロ終了でブロックする。
  [1] 解像度がルート通りか
  [2] 尺がカット計画と一致するか（±1.0s）
  [3] ラウドネスが目標±1.0LUFS内か（整音ON時）
  [4] テロップ整合（行数・重なり・尺内・文字数上限）
  [5] 目視用フレームを4枚抽出（テロップ表示中の瞬間）
出力: work/qc_report.json + work/qc_frames/*.png
"""
import argparse
import json
import re
import sys
from pathlib import Path

from common import info, load_json, save_json, run, ffprobe_info

ROUTE_SIZE = {"vertical": (1080, 1920), "horizontal": (1920, 1080)}


def measure_lufs(path):
    out = run(["ffmpeg", "-hide_banner", "-i", str(path),
               "-af", "loudnorm=print_format=json", "-f", "null", "-"], capture=True)
    m = re.search(r"\{[^{}]*\"input_i\"[\s\S]*?\}", out)
    return float(json.loads(m.group(0))["input_i"]) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    args = ap.parse_args()
    job = load_json(args.job)
    work = Path(job["work"])
    final = work / "final.mp4"

    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        info(f"  {'OK' if ok else 'NG'}  {name}: {detail}")

    info("品質改札を実行中...")
    if not final.exists():
        add("出力ファイル", False, "final.mp4 がありません")
    else:
        probe = ffprobe_info(final)
        tw, th = ROUTE_SIZE.get(job.get("route", "vertical"))
        add("解像度", (probe["width"], probe["height"]) == (tw, th),
            f"{probe['width']}x{probe['height']}（期待 {tw}x{th}）")

        plan = load_json(work / "cut_plan.json")
        diff = abs(probe["duration_s"] - plan["final_duration_s"])
        add("尺の一致", diff <= 1.0,
            f"出力 {probe['duration_s']:.2f}s / 計画 {plan['final_duration_s']:.2f}s（差 {diff:.2f}s）")

        if job.get("audio", {}).get("master", True):
            target = float(job.get("audio", {}).get("lufs", -14.0))
            lufs = measure_lufs(final)
            add("ラウドネス", lufs is not None and abs(lufs - target) <= 1.0,
                f"{lufs} LUFS（目標 {target}）")

        caps = load_json(work / "captions.json")["lines"]
        max_chars = int(job.get("telop", {}).get("max_chars", 10))
        max_lines = int(job.get("telop", {}).get("max_lines", 2))
        overlap = any(caps[i]["e"] > caps[i + 1]["s"] + 0.01 for i in range(len(caps) - 1))
        too_long = [c["text"] for c in caps
                    if max(len(l) for l in c["text"].split("\n")) > max_chars + 4
                    or len(c["text"].split("\n")) > max_lines]
        in_range = all(0 <= c["s"] < c["e"] <= probe["duration_s"] + 0.5 for c in caps)
        add("テロップ整合", not overlap and in_range and not too_long,
            f"{len(caps)}画面 / 重なり{'あり' if overlap else 'なし'} / 超過 {len(too_long)}")

        # 目視用フレーム
        frames_dir = work / "qc_frames"
        frames_dir.mkdir(exist_ok=True)
        for old in frames_dir.glob("*.png"):
            old.unlink()
        picks = caps[:: max(1, len(caps) // 4)][:4] if caps else []
        for i, c in enumerate(picks):
            t = (c["s"] + c["e"]) / 2
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(final),
                 "-frames:v", "1", str(frames_dir / f"frame_{i}.png")])
        if picks:
            info(f"  目視用フレーム {len(picks)}枚 -> {frames_dir}")

    ok = all(c["ok"] for c in checks)
    save_json(work / "qc_report.json", {"pass": ok, "checks": checks})
    info(f"品質改札: {'全通過' if ok else 'NGあり（出荷ブロック）'}")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
