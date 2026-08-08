#!/usr/bin/env python3
"""facestamp.py — 顔を自動検出して、スタンプ画像を自動で追従させる。

顔出しNGの人の動画に、亀山会長のYouTubeのような「顔スタンプ」をかぶせる。
検出 → 補間 → 平滑化 → 合成 の4段。検出が切れたフレームは直前の位置を保持する
（顔が一瞬でも出ないようにするため、必ず何かを乗せ続ける設計）。

  python3 facestamp.py --video in.mp4 --stamp stamp.png --out out.mp4

主なオプション:
  --scale 2.0        スタンプの大きさ（顔の横幅の何倍か）
  --offset-y -0.12   上下位置（顔の高さに対する比率。マイナスで上）
  --smooth 0.2       追従の滑らかさ（小さいほどヌルヌル、大きいほどキビキビ）
  --preview 8        先頭8秒だけ書き出して確認する
  --sheet check.jpg  仕上がり確認用のコンタクトシートを出す
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request

try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit(
        "opencv が入っていません。次を実行してください:\n"
        "  pip3 install opencv-python\n"
    )

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.abspath(os.path.join(HERE, "..", "assets"))
YUNET_PATH = os.path.join(ASSETS, "face_detection_yunet_2023mar.onnx")
YUNET_URL = (  # git-lfs 実体を返す media エンドポイント（raw だとポインタが降ってくる）
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
DETECT_WIDTH = 640  # 検出はこの横幅に縮めてから行う（速度のため）


# ---------------------------------------------------------------- 検出

class YuNetDetector:
    """OpenCV YuNet。正面・斜め・小さい顔に強い。目の位置も取れる。"""

    name = "yunet"
    has_landmarks = True

    def __init__(self, size, score=0.6):
        self.det = cv2.FaceDetectorYN.create(
            YUNET_PATH, "", size, score_threshold=score, nms_threshold=0.3, top_k=50
        )

    def detect(self, frame):
        h, w = frame.shape[:2]
        self.det.setInputSize((w, h))
        _, faces = self.det.detect(frame)
        out = []
        if faces is None:
            return out
        for f in faces:
            x, y, fw, fh = f[0:4]
            eyes = ((f[4], f[5]), (f[6], f[7]))  # 右目, 左目
            out.append(
                {"x": float(x), "y": float(y), "w": float(fw), "h": float(fh),
                 "score": float(f[-1]), "eyes": [[float(v) for v in e] for e in eyes]}
            )
        return out


class HaarDetector:
    """opencv に同梱の Haar カスケード。モデルDL不要のフォールバック。"""

    name = "haar"
    has_landmarks = False

    def __init__(self, size, score=None):
        base = cv2.data.haarcascades
        self.front = cv2.CascadeClassifier(base + "haarcascade_frontalface_default.xml")
        self.prof = cv2.CascadeClassifier(base + "haarcascade_profileface.xml")

    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        boxes = list(self.front.detectMultiScale(gray, 1.1, 5, minSize=(40, 40)))
        if not len(boxes):
            boxes = list(self.prof.detectMultiScale(gray, 1.1, 5, minSize=(40, 40)))
        if not len(boxes):  # 左向き（反転して再検出）
            flipped = cv2.flip(gray, 1)
            for (x, y, w, h) in self.prof.detectMultiScale(flipped, 1.1, 5, minSize=(40, 40)):
                boxes.append((gray.shape[1] - x - w, y, w, h))
        return [
            {"x": float(x), "y": float(y), "w": float(w), "h": float(h),
             "score": 1.0, "eyes": None}
            for (x, y, w, h) in boxes
        ]


def ensure_yunet(allow_download):
    if os.path.exists(YUNET_PATH):
        return True
    if not allow_download:
        return False
    os.makedirs(ASSETS, exist_ok=True)
    print(f"[facestamp] YuNet モデルを取得中… ({YUNET_URL})")
    urllib.request.urlretrieve(YUNET_URL, YUNET_PATH)
    return os.path.exists(YUNET_PATH)


def pick_face(faces, prev):
    """1人だけ追う。前フレームに近いもの、なければ一番大きいものを選ぶ。"""
    if not faces:
        return None
    if prev is None:
        return max(faces, key=lambda f: f["w"] * f["h"])
    pcx, pcy = prev["x"] + prev["w"] / 2, prev["y"] + prev["h"] / 2

    def dist(f):
        cx, cy = f["x"] + f["w"] / 2, f["y"] + f["h"] / 2
        return ((cx - pcx) ** 2 + (cy - pcy) ** 2) ** 0.5

    near = min(faces, key=dist)
    # 前の顔幅の3倍以上ワープしたら別人扱いして、大きい顔に戻す
    if dist(near) > prev["w"] * 3:
        return max(faces, key=lambda f: f["w"] * f["h"])
    return near


def scan(video, detector_name, every, score, roi=None, limit_frames=None):
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        sys.exit(f"動画を開けません: {video}")
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if limit_frames:
        total = min(total, limit_frames)

    ratio = min(1.0, DETECT_WIDTH / float(W))
    dw, dh = int(W * ratio), int(H * ratio)

    Det = {"yunet": YuNetDetector, "haar": HaarDetector}[detector_name]
    det = Det((dw, dh), score)

    raw = {}
    prev = None
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok or (limit_frames and idx >= limit_frames):
            break
        if idx % every == 0:
            small = cv2.resize(frame, (dw, dh)) if ratio < 1.0 else frame
            if roi:
                x0, y0, x1, y1 = [int(v * s) for v, s in
                                  zip(roi, (dw, dh, dw, dh))]
                crop = small[y0:y1, x0:x1]
                faces = det.detect(crop)
                for f in faces:
                    f["x"] += x0
                    f["y"] += y0
                    if f.get("eyes"):
                        f["eyes"] = [[e[0] + x0, e[1] + y0] for e in f["eyes"]]
            else:
                faces = det.detect(small)
            f = pick_face(faces, prev)
            if f:
                prev = f
                raw[idx] = {
                    "x": f["x"] / ratio, "y": f["y"] / ratio,
                    "w": f["w"] / ratio, "h": f["h"] / ratio,
                    "eyes": [[e[0] / ratio, e[1] / ratio] for e in f["eyes"]] if f.get("eyes") else None,
                }
            if idx % (every * 60) == 0:
                pct = 100.0 * idx / max(total, 1)
                print(f"\r[facestamp] 顔を検出中… {pct:5.1f}%", end="", file=sys.stderr)
        idx += 1
    cap.release()
    print("\r[facestamp] 顔を検出中… 100.0%", file=sys.stderr)
    return {"W": W, "H": H, "fps": fps, "frames": idx, "raw": raw}


# ------------------------------------------------- 補間・平滑化

def build_track(scan_res, smooth, lost_hold=0.0):
    """検出のない区間を埋めて、全フレーム分の位置を作る。

    lost_hold=0 なら、検出が切れても直前の位置を最後まで保持する（顔が出る事故を防ぐ）。
    lost_hold=N なら、最後の検出から N 秒を超えた区間はスタンプを消す（カット割りの多い動画用）。
    """
    n = scan_res["frames"]
    raw = scan_res["raw"]
    keys = sorted(raw.keys())
    if not keys:
        return None, 0.0

    track = [None] * n
    j = 0  # keys を左から追うポインタ（全フレーム走査を O(n) に保つ）
    for i in range(n):
        while j + 1 < len(keys) and keys[j + 1] <= i:
            j += 1
        lo = keys[j]
        hi = keys[j + 1] if j + 1 < len(keys) else lo
        if i <= keys[0] or lo == hi or i >= keys[-1]:
            src = raw[keys[0]] if i <= keys[0] else raw[keys[-1]] if i >= keys[-1] else raw[lo]
            track[i] = dict(src)
        else:
            t = (i - lo) / float(hi - lo)
            a, b = raw[lo], raw[hi]
            track[i] = {k: a[k] + (b[k] - a[k]) * t for k in ("x", "y", "w", "h")}
            if a.get("eyes") and b.get("eyes"):
                track[i]["eyes"] = [
                    [a["eyes"][k][d] + (b["eyes"][k][d] - a["eyes"][k][d]) * t for d in (0, 1)]
                    for k in (0, 1)
                ]
        # 一番近い検出フレームまでの距離（消すかどうかの判断に使う）
        track[i]["gap"] = min(abs(i - lo), abs(hi - i)) if hi != lo else abs(i - lo)

    # EMA（往復かけて位相ズレをなくす）
    for k in ("x", "y", "w", "h"):
        v = [p[k] for p in track]
        v = ema(v, smooth)
        v = list(reversed(ema(list(reversed(v)), smooth)))
        for i, p in enumerate(track):
            p[k] = v[i]

    limit = lost_hold * scan_res["fps"] if lost_hold > 0 else None
    for p in track:
        p["visible"] = True if limit is None else p["gap"] <= limit

    coverage = len(keys) / float(max(1, len(range(0, n, max(1, keys[1] - keys[0] if len(keys) > 1 else 1)))))
    return track, min(1.0, coverage)


def ema(values, alpha):
    out = []
    acc = values[0]
    for v in values:
        acc = alpha * v + (1 - alpha) * acc
        out.append(acc)
    return out


# ---------------------------------------------------------------- 合成

def load_stamp(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        sys.exit(f"スタンプ画像を開けません: {path}")
    if img.shape[2] == 3:
        print("[facestamp] 警告: 透過（アルファ）がないPNGです。四角いまま乗ります", file=sys.stderr)
        alpha = np.full(img.shape[:2], 255, dtype=np.uint8)
        img = np.dstack([img, alpha])
    return img


def load_stamp_face(path):
    """prep_stamp.py が残した「絵の中の顔の位置」を読む。

    無ければ絵全体を顔とみなす（= 従来どおり、絵の中心を顔の中心に合わせる）。
    帽子のつばのように顔以外が張り出した絵は、これが無いと横にずれる。
    """
    side = os.path.splitext(path)[0] + ".json"
    if os.path.exists(side):
        try:
            with open(side) as f:
                j = json.load(f)
            d = j["face"]
            return {"w": d["w"], "cx": d["x"] + d["w"] / 2, "cy": d["y"] + d["h"] / 2,
                    "recommend": j.get("recommend", {})}
        except (KeyError, ValueError):
            print(f"[facestamp] {side} を読めなかったので絵全体を顔として扱います", file=sys.stderr)
    return {"w": 1.0, "cx": 0.5, "cy": 0.5, "recommend": {}}


def rotate_rgba(img, deg):
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    m[0, 2] += nw / 2 - w / 2
    m[1, 2] += nh / 2 - h / 2
    return cv2.warpAffine(img, m, (nw, nh), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))


def blend(frame, stamp, cx, cy):
    """frame に stamp を (cx, cy) 中心でアルファ合成する。はみ出し分は切り取る。"""
    sh, sw = stamp.shape[:2]
    H, W = frame.shape[:2]
    x0, y0 = int(round(cx - sw / 2)), int(round(cy - sh / 2))
    sx0, sy0 = max(0, -x0), max(0, -y0)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(W, x0 + sw - sx0), min(H, y0 + sh - sy0)
    if x1 <= x0 or y1 <= y0:
        return
    crop = stamp[sy0:sy0 + (y1 - y0), sx0:sx0 + (x1 - x0)]
    a = crop[:, :, 3:4].astype(np.float32) / 255.0
    roi = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = (roi * (1 - a) + crop[:, :, :3].astype(np.float32) * a).astype(np.uint8)


def has_audio(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True)
    return bool(r.stdout.strip())


def render(video, out, track, stamp_img, args, sface=None, limit_frames=None):
    cap = cv2.VideoCapture(video)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = limit_frames or int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", f"{fps}",
           "-i", "-"]
    audio = has_audio(video)
    if audio:
        cmd += ["-i", video, "-map", "0:v:0", "-map", "1:a:0", "-c:a", "copy"]
    if args.encoder == "videotoolbox":
        cmd += ["-c:v", "h264_videotoolbox", "-b:v", args.bitrate]
    else:
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]
    cmd += ["-pix_fmt", "yuv420p", "-shortest", out]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    cache = {}
    uncovered = 0
    hidden = 0
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok or (limit_frames and idx >= limit_frames):
            break
        p = track[min(idx, len(track) - 1)]
        if not p.get("visible", True):
            proc.stdin.write(frame.tobytes())
            hidden += 1
            idx += 1
            continue
        # --scale は「絵の顔が、検出した顔の何倍か」。絵全体はそこから逆算する
        target_w = max(8.0, p["w"] * args.scale / sface["w"])
        # 2px刻みに量子化してリサイズ結果を使い回す（速度＆サイズのチラつき防止）
        qw = int(round(target_w / 2.0)) * 2
        deg = 0.0
        if args.rotate and p.get("eyes"):
            (rx, ry), (lx, ly) = p["eyes"]
            deg = -np.degrees(np.arctan2(ly - ry, lx - rx))
            deg = round(max(-25.0, min(25.0, deg)) / 2.0) * 2.0
        key = (qw, deg)
        if key not in cache:
            base = rotate_rgba(stamp_img, deg) if deg else stamp_img
            sh, sw = base.shape[:2]
            nh = max(2, int(round(qw * sh / float(sw))))
            cache[key] = cv2.resize(base, (max(2, qw), nh), interpolation=cv2.INTER_AREA)
            if len(cache) > 400:
                cache.clear()
        st = cache[key]
        sh, sw = st.shape[:2]
        # 絵の中の顔の位置が、実際の顔の位置に来るように全体をずらす
        cx = p["x"] + p["w"] / 2 + args.offset_x * p["w"] - (sface["cx"] - 0.5) * sw
        cy = p["y"] + p["h"] / 2 + args.offset_y * p["h"] - (sface["cy"] - 0.5) * sh
        if args.edge == "clamp":  # 画面からはみ出さないように内側へ寄せる
            if sw <= W:
                cx = min(max(cx, sw / 2), W - sw / 2)
            if sh <= H:
                cy = min(max(cy, sh / 2), H - sh / 2)
        # 顔がスタンプからはみ出していないかの自己チェック
        if not (cx - sw / 2 <= p["x"] and cx + sw / 2 >= p["x"] + p["w"]
                and cy - sh / 2 <= p["y"] and cy + sh / 2 >= p["y"] + p["h"]):
            uncovered += 1
        blend(frame, st, cx, cy)
        proc.stdin.write(frame.tobytes())
        if idx % 60 == 0:
            print(f"\r[facestamp] 書き出し中… {100.0 * idx / max(total, 1):5.1f}%",
                  end="", file=sys.stderr)
        idx += 1
    cap.release()
    proc.stdin.close()
    proc.wait()
    print("\r[facestamp] 書き出し中… 100.0%", file=sys.stderr)
    return idx, uncovered, hidden


def contact_sheet(video, path, cols=4, rows=3):
    cap = cv2.VideoCapture(video)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    n = cols * rows
    tiles = []
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * (i + 0.5) / n))
        ok, f = cap.read()
        if not ok:
            break
        tiles.append(cv2.resize(f, (320, int(320 * f.shape[0] / f.shape[1]))))
    cap.release()
    if not tiles:
        return
    th, tw = tiles[0].shape[:2]
    sheet = np.zeros((th * rows, tw * cols, 3), dtype=np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        sheet[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = t
    cv2.imwrite(path, sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--stamp", required=True, help="透過PNGのスタンプ画像")
    ap.add_argument("--out", help="出力mp4（省略時は <元の名前>_stamped.mp4）")
    ap.add_argument("--scale", type=float, help="絵の顔を、検出した顔の何倍にするか（既定2.0）")
    ap.add_argument("--offset-x", type=float, help="左右の微調整（顔幅に対する比率）")
    ap.add_argument("--offset-y", type=float, help="上下の微調整（プラスで下へ）")
    ap.add_argument("--smooth", type=float, default=0.2, help="0.05=ヌルヌル 0.5=キビキビ")
    ap.add_argument("--every", type=int, default=2, help="何フレームおきに検出するか")
    ap.add_argument("--score", type=float, default=0.6, help="検出のしきい値(yunet)")
    ap.add_argument("--detector", choices=["auto", "yunet", "haar"], default="auto")
    ap.add_argument("--edge", choices=["clamp", "free"], default="clamp",
                    help="clamp=画面外にはみ出させない")
    ap.add_argument("--rotate", action="store_true", help="顔の傾きにスタンプを合わせる")
    ap.add_argument("--lost-hold", type=float, default=0.0,
                    help="検出が切れてから何秒でスタンプを消すか。0=消さずに保持（既定・安全側）")
    ap.add_argument("--preview", type=float, default=0, help="先頭N秒だけ書き出す")
    ap.add_argument("--sheet", help="確認用コンタクトシートの出力先(.jpg)")
    ap.add_argument("--track-json", help="検出結果の保存先")
    ap.add_argument("--encoder", choices=["x264", "videotoolbox"], default="x264")
    ap.add_argument("--bitrate", default="12M")
    ap.add_argument("--no-download", action="store_true", help="モデルを自動取得しない")
    ap.add_argument("--strict", action="store_true",
                    help="顔がスタンプから出た可能性が1フレームでもあれば異常終了する")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg が見つかりません")
    if not os.path.exists(args.video):
        sys.exit(f"動画がありません: {args.video}")

    detector = args.detector
    if detector in ("auto", "yunet"):
        if ensure_yunet(not args.no_download):
            detector = "yunet"
        elif detector == "yunet":
            sys.exit("YuNet モデルがありません（--detector haar で代替できます）")
        else:
            print("[facestamp] YuNet が無いので haar で代替します", file=sys.stderr)
            detector = "haar"

    out = args.out or os.path.splitext(args.video)[0] + "_stamped.mp4"
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()
    limit = int(args.preview * fps) if args.preview else None

    res = scan(args.video, detector, max(1, args.every), args.score, limit_frames=limit)
    if not res["raw"]:
        sys.exit("顔が1つも検出できませんでした。--detector haar / --score 0.4 を試すか、"
                 "明るさ・顔の大きさを確認してください")
    track, _ = build_track(res, max(0.01, min(1.0, args.smooth)), args.lost_hold)

    sampled = len(range(0, res["frames"], max(1, args.every)))
    coverage = 100.0 * len(res["raw"]) / max(1, sampled)

    if args.track_json:
        with open(args.track_json, "w") as f:
            json.dump({"fps": res["fps"], "W": res["W"], "H": res["H"],
                       "detector": detector, "coverage": coverage,
                       "track": track}, f, ensure_ascii=False)

    stamp = load_stamp(args.stamp)
    sface = load_stamp_face(args.stamp)

    # 指定が無ければ、そのスタンプ用に調整済みの値 → それも無ければ既定値
    rec = sface.get("recommend", {})
    tuned = []
    for key, fallback in (("scale", 2.0), ("offset_x", 0.0), ("offset_y", 0.0)):
        if getattr(args, key) is None:
            setattr(args, key, rec.get(key, fallback))
            if key in rec:
                tuned.append(f"{key}={rec[key]}")
    if tuned:
        print(f"[facestamp] このスタンプ用の調整値を使います: {' '.join(tuned)}")

    frames, uncovered, hidden = render(args.video, out, track, stamp, args, sface,
                                       limit_frames=limit)

    print(f"\n[facestamp] 完了: {out}")
    print(f"  検出器      : {detector}")
    if sface["w"] < 1.0:
        print(f"  絵の顔位置  : 幅{sface['w'] * 100:.0f}% 中心({sface['cx'] * 100:.0f}%,"
              f"{sface['cy'] * 100:.0f}%) を使って自動で位置合わせ")
    print(f"  顔の検出率  : {coverage:.1f}%（残りは前後から補間・保持）")
    if args.lost_hold:
        print(f"  スタンプ無し: {hidden} / {frames} フレーム（--lost-hold {args.lost_hold}秒 の設定による）")
    print(f"  はみ出し    : {uncovered} / {frames} フレームで顔がスタンプから出た可能性")
    if uncovered:
        print("  → --scale を上げるか --offset-y を調整してください")
    if args.sheet:
        contact_sheet(out, args.sheet)
        print(f"  確認シート  : {args.sheet}")
    if args.strict and uncovered:
        sys.exit(3)


if __name__ == "__main__":
    main()
