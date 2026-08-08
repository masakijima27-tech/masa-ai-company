#!/usr/bin/env python3
"""word単位の文字起こし。バックエンドは自動判別:
  1. mlx-whisper   (Mac Apple Silicon)
  2. faster-whisper (Windows / CUDA / Linux)
  3. whisper-cli    (whisper.cpp — どの環境でも動くフォールバック)
出力: work/words.json  {"backend":..., "words":[{"w","s","e"},...], "text":...}
"""
import argparse
import json
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from common import die, info, save_json, run, find_whisper_model, normalize_text


def extract_wav(src, work):
    wav = Path(work) / "audio16k.wav"
    info("音声を抽出中 (16kHz mono)...")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
         "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)])
    return wav


def try_mlx(wav, lang):
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return None
    try:
        import mlx_whisper  # noqa
    except ImportError:
        return None
    info("バックエンド: mlx-whisper (Apple Silicon)")
    res = mlx_whisper.transcribe(
        str(wav), path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
        language=lang, word_timestamps=True)
    words = []
    for seg in res.get("segments", []):
        for w in seg.get("words", []):
            words.append({"w": normalize_text(w["word"]), "s": round(w["start"], 3), "e": round(w["end"], 3)})
    return {"backend": "mlx-whisper", "words": words}


def try_faster(wav, lang):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    info("バックエンド: faster-whisper")
    model = WhisperModel("large-v3-turbo", compute_type="auto")
    segments, _ = model.transcribe(str(wav), language=lang, word_timestamps=True)
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"w": normalize_text(w.word), "s": round(w.start, 3), "e": round(w.end, 3)})
    return {"backend": "faster-whisper", "words": words}


def try_whisper_cli(wav, lang):
    cli = shutil.which("whisper-cli")
    if not cli:
        return None
    model = find_whisper_model()
    if not model:
        die("whisperモデルがありません。doctor.py を実行してモデルをダウンロードしてください。")
    info(f"バックエンド: whisper-cli / モデル: {Path(model).name}")
    with tempfile.TemporaryDirectory() as td:
        out_base = Path(td) / "tr"
        # -ojf: トークン単位の時刻が入ったフルJSONを出力
        run([cli, "-m", model, "-f", str(wav), "-l", lang,
             "-ojf", "-of", str(out_base), "-np"], capture=True)
        data = json.loads((out_base.with_suffix(".json")).read_text(encoding="utf-8"))
    words = []
    for seg in data.get("transcription", []):
        for tok in seg.get("tokens", []):
            raw = tok.get("text", "")
            if raw.startswith("[_"):  # [_BEG_] などの特殊トークン
                continue
            text = normalize_text(raw)
            if not text or text.startswith("[") or text.startswith("("):
                continue  # [音楽] などの非音声タグ
            off = tok["offsets"]
            words.append({"w": text, "s": round(off["from"] / 1000, 3), "e": round(off["to"] / 1000, 3)})
    return {"backend": "whisper-cli", "words": words}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--lang", default="ja")
    args = ap.parse_args()

    Path(args.work).mkdir(parents=True, exist_ok=True)
    wav = extract_wav(args.src, args.work)

    result = try_mlx(wav, args.lang) or try_faster(wav, args.lang) or try_whisper_cli(wav, args.lang)
    if result is None:
        die("文字起こしバックエンドがありません。mlx-whisper / faster-whisper / whisper-cli のいずれかを導入してください（INSTALL.md参照）。")

    words = [w for w in result["words"] if w["w"]]
    result["words"] = words
    result["text"] = "".join(w["w"] for w in words)
    out = Path(args.work) / "words.json"
    save_json(out, result)
    info(f"文字起こし完了: {len(words)} words -> {out}")


if __name__ == "__main__":
    main()
