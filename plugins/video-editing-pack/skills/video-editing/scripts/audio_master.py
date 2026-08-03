#!/usr/bin/env python3
"""2パス整音: loudnorm でラウドネスを -14LUFS（配信標準）に揃える。
pass1で計測 → pass2でlinearモード適用。低域ノイズはハイパス70Hzで軽減。
入力: work/cut.mp4 → 出力: work/mastered.mp4（映像は無劣化コピー）
"""
import argparse
import json
import re
from pathlib import Path

from common import die, info, load_json, run

def measure(src, i_target, tp, lra):
    out = run(["ffmpeg", "-hide_banner", "-i", str(src),
               "-af", f"highpass=f=70,loudnorm=I={i_target}:TP={tp}:LRA={lra}:print_format=json",
               "-f", "null", "-"], capture=True)
    m = re.search(r"\{[^{}]*\"input_i\"[\s\S]*?\}", out)
    if not m:
        die("loudnorm計測結果を取得できませんでした")
    return json.loads(m.group(0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    args = ap.parse_args()
    job = load_json(args.job)
    work = Path(job["work"])
    src = work / "cut_final.mp4"
    if not src.exists():
        die("cut_final.mp4 がありません。先に jetcut.py を実行してください。")

    audio = job.get("audio", {})
    if not audio.get("master", True):
        info("整音スキップ（audio.master=false）。cut.mp4 をそのまま使用します")
        (work / "mastered.mp4").unlink(missing_ok=True)
        import shutil
        shutil.copy2(src, work / "mastered.mp4")
        return

    i_target = float(audio.get("lufs", -14.0))
    tp, lra = -1.0, 11
    info("整音 1/2: ラウドネス計測中...")
    m = measure(src, i_target, tp, lra)
    info(f"  入力: {m['input_i']} LUFS / TP {m['input_tp']} dB")

    info(f"整音 2/2: {i_target} LUFS へ調整中...")
    af = (f"highpass=f=70,loudnorm=I={i_target}:TP={tp}:LRA={lra}"
          f":measured_I={m['input_i']}:measured_TP={m['input_tp']}"
          f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
          f":offset={m['target_offset']}:linear=true")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
         "-af", af, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         str(work / "mastered.mp4")])
    info(f"整音完了 -> {work / 'mastered.mp4'}")


if __name__ == "__main__":
    main()
