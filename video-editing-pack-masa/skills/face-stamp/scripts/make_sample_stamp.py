#!/usr/bin/env python3
"""動作確認用のサンプルスタンプ（透過PNG）を作る。

本番は本人のイラストを使うこと。これはあくまで位置合わせ確認用。
  python3 make_sample_stamp.py ../assets/sample_stamp.png
"""
import sys

from PIL import Image, ImageDraw

S = 900
CREAM = (247, 231, 206, 255)
INK = (26, 26, 26, 255)


def main(out):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 輪郭（縦長のたまご型）
    face = (S * 0.18, S * 0.14, S * 0.82, S * 0.90)
    d.ellipse(face, fill=CREAM, outline=INK, width=16)

    # 髪（頭頂の黒いかたまり）
    d.pieslice((S * 0.15, S * 0.08, S * 0.85, S * 0.62), 180, 360, fill=INK)
    d.polygon([(S * 0.16, S * 0.34), (S * 0.30, S * 0.16), (S * 0.34, S * 0.36)], fill=INK)
    d.polygon([(S * 0.84, S * 0.34), (S * 0.70, S * 0.16), (S * 0.66, S * 0.36)], fill=INK)

    # 目（半目・線でつくる）
    for cx in (S * 0.37, S * 0.63):
        d.polygon([(cx - S * 0.10, S * 0.52), (cx + S * 0.10, S * 0.50),
                   (cx + S * 0.10, S * 0.56), (cx - S * 0.10, S * 0.58)], fill=(255, 255, 255, 255),
                  outline=INK)
        d.line([(cx - S * 0.10, S * 0.52), (cx + S * 0.10, S * 0.50)], fill=INK, width=10)
        d.ellipse((cx - S * 0.02, S * 0.515, cx + S * 0.03, S * 0.565), fill=INK)

    # 眉
    d.line([(S * 0.28, S * 0.44), (S * 0.44, S * 0.42)], fill=INK, width=9)
    d.line([(S * 0.56, S * 0.42), (S * 0.72, S * 0.44)], fill=INK, width=9)

    # 口
    d.arc((S * 0.42, S * 0.64, S * 0.58, S * 0.76), 200, 340, fill=INK, width=9)

    img.save(out)
    print(f"書き出しました: {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sample_stamp.png")
