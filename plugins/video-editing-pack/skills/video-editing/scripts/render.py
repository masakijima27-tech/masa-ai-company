#!/usr/bin/env python3
"""テロップ焼き込み。
Pillowで各行を透過PNGに描画（縁取り＋ドロップシャドウ）し、
ffmpeg overlay の enable='between(t,s,e)' で表示区間だけ合成する。
libass/drawtext非搭載のffmpegでも動く方式。
入力: work/mastered.mp4 + captions.json → 出力: work/final.mp4
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from common import die, info, load_json, run, find_font

ROUTE_STYLE = {
    "vertical":   {"size": (1080, 1920), "color": "#FFFFFF", "y_ratio": 0.74, "font_ratio": 0.068},
    "horizontal": {"size": (1920, 1080), "color": "#FFDC32", "y_ratio": 0.86, "font_ratio": 0.052},
}
CHUNK = 50  # 1パスで焼き込むテロップ数（ffmpeg入力数の上限対策）


def render_png(text, width, font_path, font_px, fill, out_path):
    """1〜2行のテロップを透過PNGに描画（センター揃え・縁取り・ドロップシャドウ）"""
    def measure(font, stroke, spacing):
        return ImageDraw.Draw(Image.new("RGBA", (10, 10))).multiline_textbbox(
            (0, 0), text, font=font, stroke_width=stroke, spacing=spacing, align="center")

    stroke = max(2, int(font_px * 0.11))
    spacing = int(font_px * 0.28)
    shadow_off = (int(font_px * 0.05), int(font_px * 0.10))
    font = ImageFont.truetype(font_path, font_px)
    # 長すぎる行はフォントを縮めて収める
    max_w = int(width * 0.94)
    while font_px > 20:
        bbox = measure(font, stroke, spacing)
        if bbox[2] - bbox[0] <= max_w:
            break
        font_px = int(font_px * 0.94)
        stroke = max(2, int(font_px * 0.11))
        spacing = int(font_px * 0.28)
        font = ImageFont.truetype(font_path, font_px)

    bbox = measure(font, stroke, spacing)
    tw, th = int(bbox[2] - bbox[0] + 1), int(bbox[3] - bbox[1] + 1)
    pad = stroke + max(shadow_off) + 4
    img = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    origin = (pad - bbox[0], pad - bbox[1])
    # 影 → 縁取り付き本体
    d.multiline_text((origin[0] + shadow_off[0], origin[1] + shadow_off[1]), text,
                     font=font, fill=(0, 0, 0, 150), stroke_width=stroke,
                     stroke_fill=(0, 0, 0, 150), spacing=spacing, align="center")
    d.multiline_text(origin, text, font=font, fill=fill, stroke_width=stroke,
                     stroke_fill="#000000", spacing=spacing, align="center")
    img.save(out_path)
    return img.size


def burn(video_in, video_out, entries, width, y_center, audio_copy=True):
    """entries: [(png_path, s, e, (w,h)), ...] を1パスで焼き込む"""
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video_in)]
    for png, *_ in entries:
        cmd += ["-i", str(png)]
    fc, cur = [], "[0:v]"
    for i, (_, s, e, (w, h)) in enumerate(entries):
        out = f"[v{i}]" if i < len(entries) - 1 else "[vo]"
        x = f"(main_w-{w})/2"
        y = int(y_center - h / 2)
        fc.append(f"{cur}[{i + 1}]overlay=x={x}:y={y}:enable='between(t,{s},{e})'{out}")
        cur = f"[v{i}]"
    cmd += ["-filter_complex", ";".join(fc), "-map", "[vo]", "-map", "0:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-c:a", "copy", str(video_out)]
    run(cmd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    args = ap.parse_args()
    job = load_json(args.job)
    work = Path(job["work"])
    route = job.get("route", "vertical")
    style = dict(ROUTE_STYLE.get(route, ROUTE_STYLE["vertical"]))
    telop = job.get("telop", {})

    src = work / "mastered.mp4"
    if not src.exists():
        die("mastered.mp4 がありません。先に audio_master.py を実行してください。")
    caps = load_json(work / "captions.json")["lines"]
    final = work / "final.mp4"

    if not caps:
        info("テロップ行がゼロのため、焼き込みなしでコピーします")
        import shutil
        shutil.copy2(src, final)
        return

    W, H = style["size"]
    color = telop.get("color", style["color"])
    y_center = int(float(telop.get("y_ratio", style["y_ratio"])) * H)
    font_px = int(W * float(telop.get("font_ratio", style["font_ratio"])))
    font_path = telop.get("font") or find_font()

    cap_dir = work / "caps"
    cap_dir.mkdir(exist_ok=True)
    entries = []
    for i, ln in enumerate(caps):
        png = cap_dir / f"cap_{i:04d}.png"
        size = render_png(ln["text"], W, font_path, font_px, color, png)
        entries.append((png, ln["s"], ln["e"], size))
    info(f"テロップPNG {len(entries)}枚生成（font {font_px}px / {color}）")

    # チャンク分割して多段焼き込み
    chunks = [entries[i:i + CHUNK] for i in range(0, len(entries), CHUNK)]
    cur_in = src
    for ci, chunk in enumerate(chunks):
        out = final if ci == len(chunks) - 1 else work / f"burn_pass{ci}.mp4"
        info(f"焼き込み {ci + 1}/{len(chunks)} ...")
        burn(cur_in, out, chunk, W, y_center)
        if cur_in != src and cur_in.name.startswith("burn_pass"):
            cur_in.unlink(missing_ok=True)
        cur_in = out
    info(f"焼き込み完了 -> {final}")


if __name__ == "__main__":
    main()
