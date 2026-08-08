#!/usr/bin/env python3
"""prep_stamp.py — 手持ちのイラストを、スタンプとして使える透過PNGに整える。

やること3つ:
  1. 背景（四隅から繋がっている一様な色）だけを透明にする
  2. 縁を少しぼかしてギザギザを取る
  3. まわりの余白を詰める（顔幅に対する倍率指定を効かせるため）

顔や白いハイライトのように「背景と色は近いが囲まれている」部分は消えない
（四隅から塗りつぶしで辿れる範囲だけを背景とみなすため）。

  python3 prep_stamp.py 元画像.png ../assets/masa_stamp.png
  python3 prep_stamp.py 元画像.png out.png --tol 24 --check check.png
"""

import argparse
import json
import os
import sys

try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit("opencv が必要です。先に setup_env.sh を実行してください")


def cut_background(img, tol, feather):
    """四隅から繋がっている背景だけを透明にした RGBA を返す。"""
    if img.shape[2] == 4 and img[:, :, 3].min() < 250:
        return img  # すでに透過済みなら触らない
    bgr = img[:, :, :3].copy()
    h, w = bgr.shape[:2]
    mask = np.zeros((h + 2, w + 2), np.uint8)
    flags = 4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8)
    for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        cv2.floodFill(bgr, mask, seed, 0,
                      (tol,) * 3, (tol,) * 3, flags)
    bg = mask[1:-1, 1:-1]

    alpha = np.where(bg > 0, 0, 255).astype(np.uint8)
    # 取りこぼした背景の粒（穴）を掃除してから、縁をなじませる
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    if feather > 0:
        k = feather * 2 + 1
        alpha = cv2.GaussianBlur(alpha, (k, k), 0)
        # ぼかすと絵の内側まで薄くなるので、中は不透明に戻す
        core = cv2.erode((alpha > 200).astype(np.uint8) * 255,
                         np.ones((feather + 1, feather + 1), np.uint8))
        alpha = np.maximum(alpha, core)
    return np.dstack([img[:, :, :3], alpha])


def trim(rgba, pad_ratio=0.02):
    ys, xs = np.where(rgba[:, :, 3] > 12)
    if not len(xs):
        sys.exit("絵の部分が見つかりませんでした（--tol を下げてください）")
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    pad = int(max(x1 - x0, y1 - y0) * pad_ratio)
    h, w = rgba.shape[:2]
    return rgba[max(0, y0 - pad):min(h, y1 + pad + 1),
                max(0, x0 - pad):min(w, x1 + pad + 1)]


def find_face(rgba):
    """絵の中の「顔（肌色）」の位置を測って、画像に対する比率で返す。

    帽子のつばのように顔以外が大きく張り出している絵だと、
    絵の中心＝顔の中心にならない。ここで測った矩形を facestamp.py が使って、
    絵のどこを実際の顔に重ねるかを決める。
    """
    b, g, r = (rgba[:, :, i].astype(np.int16) for i in range(3))
    a = rgba[:, :, 3]
    skin = ((r > 190) & (r > b + 25) & (r > g + 10) & (g > b) & (a > 128)).astype(np.uint8)
    skin = cv2.morphologyEx(skin, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(skin, 8)
    if n <= 1:
        return None
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    if stats[i, cv2.CC_STAT_AREA] < 0.02 * rgba.shape[0] * rgba.shape[1]:
        return None  # 肌色が小さすぎる＝顔として測れていない
    x, y, w, h = (stats[i, k] for k in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP,
                                        cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
    H, W = rgba.shape[:2]
    return {"x": x / W, "y": y / H, "w": w / W, "h": h / H}


def checker(rgba, cell=24, face=None):
    """透過の確認用に市松模様の上へ重ねた画像を作る（測った顔の枠も描く）。"""
    h, w = rgba.shape[:2]
    bgc = np.zeros((h, w, 3), np.uint8)
    yy, xx = np.mgrid[0:h, 0:w]
    bgc[:] = np.where((((yy // cell) + (xx // cell)) % 2)[..., None], 210, 245)
    a = rgba[:, :, 3:4].astype(np.float32) / 255.0
    out = (bgc * (1 - a) + rgba[:, :, :3] * a).astype(np.uint8)
    if face:
        p = (int(face["x"] * w), int(face["y"] * h),
             int(face["w"] * w), int(face["h"] * h))
        cv2.rectangle(out, (p[0], p[1]), (p[0] + p[2], p[1] + p[3]), (0, 0, 255), 4)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--tol", type=int, default=20, help="背景とみなす色の許容幅")
    ap.add_argument("--feather", type=int, default=1, help="縁のぼかし(px)")
    ap.add_argument("--pad", type=float, default=0.02, help="残す余白(長辺比)")
    ap.add_argument("--check", help="市松模様つき確認画像の出力先")
    ap.add_argument("--no-face", action="store_true", help="絵の中の顔位置を測らない")
    args = ap.parse_args()

    img = cv2.imread(args.src, cv2.IMREAD_UNCHANGED)
    if img is None:
        sys.exit(f"画像を開けません: {args.src}")
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 3:
        img = np.dstack([img, np.full(img.shape[:2], 255, np.uint8)])

    before = img.shape[:2]
    out = trim(cut_background(img, args.tol, args.feather), args.pad)
    cv2.imwrite(args.dst, out)

    opaque = float((out[:, :, 3] > 128).mean()) * 100
    print(f"書き出し: {args.dst}")
    print(f"  サイズ  : {before[1]}x{before[0]} → {out.shape[1]}x{out.shape[0]}")
    print(f"  不透明率: {opaque:.1f}%（背景が抜けていれば 40〜75% くらいが目安）")
    if opaque > 92:
        print("  ※ 背景がほとんど抜けていません。--tol を上げてください")

    face = None if args.no_face else find_face(out)
    if face:
        side = os.path.splitext(args.dst)[0] + ".json"
        with open(side, "w") as f:
            json.dump({"face": face}, f)
        print(f"  絵の中の顔: 幅{face['w'] * 100:.0f}% 中心({(face['x'] + face['w'] / 2) * 100:.0f}%, "
              f"{(face['y'] + face['h'] / 2) * 100:.0f}%) → {os.path.basename(side)} に保存")
        print("   （facestamp.py がこれを読んで、絵の顔を実際の顔に自動で合わせます）")
    else:
        print("  絵の中の顔: 測れませんでした（絵の中心を顔の中心とみなして合成されます）")

    if args.check:
        cv2.imwrite(args.check, checker(out, face=face))
        print(f"  確認用  : {args.check}")


if __name__ == "__main__":
    main()
