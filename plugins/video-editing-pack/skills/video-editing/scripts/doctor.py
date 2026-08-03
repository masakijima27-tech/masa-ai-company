#!/usr/bin/env python3
"""環境チェック（コンサル生の初回セットアップ用）。
足りないものと、その入れ方だけを表示する。--download-model でモデル取得も行う。
"""
import argparse
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from common import ASSETS, MODEL_DIR, find_whisper_model

MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{name}.bin"
RECOMMENDED_MODEL = "large-v3-turbo"  # 高精度。マシンが古い場合は small


def check(label, ok, hint=""):
    mark = "OK" if ok else "NG"
    line = f"  [{mark}] {label}"
    if not ok and hint:
        line += f"\n        -> {hint}"
    print(line)
    return ok


def has_module(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download-model", nargs="?", const=RECOMMENDED_MODEL,
                    help="whisperモデルをダウンロード（既定: large-v3-turbo / 軽量なら small を指定）")
    args = ap.parse_args()

    if args.download_model:
        name = args.download_model
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        dst = MODEL_DIR / f"ggml-{name}.bin"
        if dst.exists():
            print(f"モデルは既にあります: {dst}")
        else:
            url = MODEL_URL.format(name=name)
            print(f"ダウンロード中: {url}\n  -> {dst}（数百MB〜1.6GB、数分かかります）")
            urllib.request.urlretrieve(url, dst)
            print("完了")
        return

    print("================ video-editing 環境チェック ================")
    ok = True
    ok &= check("Python 3.9+", sys.version_info >= (3, 9), "python.org から最新版をインストール")
    ok &= check("ffmpeg", shutil.which("ffmpeg") is not None,
                "Mac: brew install ffmpeg / Windows: winget install ffmpeg")
    ok &= check("Pillow（画像描画）", has_module("PIL"), "pip3 install pillow")

    is_arm_mac = platform.system() == "Darwin" and platform.machine() == "arm64"
    backends = []
    if is_arm_mac and has_module("mlx_whisper"):
        backends.append("mlx-whisper")
    if has_module("faster_whisper"):
        backends.append("faster-whisper")
    if shutil.which("whisper-cli"):
        backends.append("whisper-cli")
    hint = ("Mac(Apple Silicon): pip3 install mlx-whisper / "
            "Windows: pip3 install faster-whisper / "
            "古いMacなど: brew install whisper-cpp")
    ok &= check(f"文字起こしエンジン（{' , '.join(backends) or 'なし'}）", bool(backends), hint)

    if "whisper-cli" in backends and not any(b in backends for b in ("mlx-whisper", "faster-whisper")):
        model = find_whisper_model()
        ok &= check(f"whisperモデル（{Path(model).name if model else '未取得'}）", model is not None,
                    "python3 doctor.py --download-model small （高精度なら引数なしで large-v3-turbo）")

    try:
        from common import find_font
        from PIL import ImageFont
        font_path = find_font()
        ImageFont.truetype(font_path, 40)
        font_ok, font_name = True, Path(font_path).name
    except SystemExit:
        font_ok, font_name = False, "なし"
    except Exception:
        font_ok, font_name = False, "読込失敗"
    ok &= check(f"テロップ用フォント（{font_name}）", font_ok,
                "Noto Sans JP Black を assets/fonts/NotoSansCJKjp-Black.otf に配置 "
                "(https://github.com/notofonts/noto-cjk の Sans/OTF/Japanese)")

    print("=====================================================")
    print("すべてOKです。動画パスを渡して使い始められます。" if ok
          else "NG項目を上のヒント通りに解消してから再実行してください。")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
