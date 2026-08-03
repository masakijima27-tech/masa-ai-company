#!/usr/bin/env python3
"""納品物の出力。
  mp4    : final.mp4 を出力先へコピー
  srt    : captions.json から SRT 字幕（カット後タイムライン）
  fcpxml : カット済みタイムライン（keep区間を並べたFCPXML 1.10）を生成
           → Final Cut Pro に読み込んでそのまま続きを編集できる
"""
import argparse
import shutil
from fractions import Fraction
from pathlib import Path
from xml.sax.saxutils import escape

from common import die, info, load_json, fmt_ts, ffprobe_info


def write_srt(caps, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, c in enumerate(caps, 1):
            f.write(f"{i}\n{fmt_ts(c['s'])} --> {fmt_ts(c['e'])}\n{c['text']}\n\n")


def rational(sec, fps: Fraction) -> str:
    """秒 → フレーム境界に整列したFCPXML時間表記"""
    frames = round(sec * fps)
    return f"{frames * fps.denominator}/{fps.numerator}s"


def write_fcpxml(src, probe, keeps, path, project_name):
    fps = Fraction(probe["fps_num"], probe["fps_den"])
    fd = f"{fps.denominator}/{fps.numerator}s"
    w, h = probe["width"], probe["height"]
    src_uri = Path(src).resolve().as_uri()
    total = sum(e - s for s, e in keeps)

    clips = []
    offset = 0.0
    for s, e in keeps:
        clips.append(
            f'        <asset-clip name="{escape(Path(src).stem)}" ref="a1" '
            f'offset="{rational(offset, fps)}" start="{rational(s, fps)}" '
            f'duration="{rational(e - s, fps)}" audioRole="dialogue"/>')
        offset += e - s

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.10">
  <resources>
    <format id="f1" name="FFVideoFormatRateUndefined" frameDuration="{fd}" width="{w}" height="{h}"/>
    <asset id="a1" name="{escape(Path(src).stem)}" start="0s" duration="{rational(probe['duration_s'], fps)}" hasVideo="1" hasAudio="1" format="f1">
      <media-rep kind="original-media" src="{escape(src_uri)}"/>
    </asset>
  </resources>
  <library>
    <event name="video-editing">
      <project name="{escape(project_name)}">
        <sequence format="f1" duration="{rational(total, fps)}" tcStart="0s" tcFormat="NDF">
          <spine>
{chr(10).join(clips)}
          </spine>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>
"""
    Path(path).write_text(xml, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    args = ap.parse_args()
    job = load_json(args.job)
    work = Path(job["work"])
    outputs = job.get("outputs", ["mp4"])
    out_dir = Path(job.get("out_dir") or Path(job["src"]).parent)
    stem = job.get("stem") or Path(job["src"]).stem

    caps = load_json(work / "captions.json")["lines"]

    made = []
    if "mp4" in outputs:
        final = work / "final.mp4"
        if not final.exists():
            die("final.mp4 がありません")
        dst = out_dir / f"{stem}_edited.mp4"
        shutil.copy2(final, dst)
        made.append(dst)
    if "srt" in outputs:
        dst = out_dir / f"{stem}_edited.srt"
        write_srt(caps, dst)
        made.append(dst)
    if "fcpxml" in outputs:
        plan = load_json(work / "cut_plan.json")
        probe = job.get("src_info") or ffprobe_info(job["src"])
        dst = out_dir / f"{stem}_edited.fcpxml"
        write_fcpxml(job["src"], probe, plan["keeps_src_final"], dst, stem)
        made.append(dst)

    for m in made:
        info(f"納品: {m}")


if __name__ == "__main__":
    main()
