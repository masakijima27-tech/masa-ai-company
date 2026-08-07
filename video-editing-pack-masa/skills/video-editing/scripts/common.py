# video-editing 共通ユーティリティ
import json
import os
import re
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[3]  # scripts -> video-editing -> skills -> pack root
ASSETS = PACK_ROOT / "assets"
MODEL_DIR = Path(os.environ.get("VIDEO_EDITING_MODEL_DIR", Path.home() / ".cache" / "video-editing" / "models"))

FONT_CANDIDATES = [
    ASSETS / "fonts" / "NotoSansCJKjp-Black.otf",
    Path("/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc"),
    Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
    Path("C:/Windows/Fonts/meiryob.ttc"),
    Path("C:/Windows/Fonts/YuGothB.ttc"),
]


def die(msg: str, code: int = 1):
    print(f"[video-editing] エラー: {msg}", file=sys.stderr)
    sys.exit(code)


def info(msg: str):
    print(f"[video-editing] {msg}", flush=True)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def which_ffmpeg():
    for name in ("ffmpeg",):
        p = shutil.which(name)
        if p:
            return p
    die("ffmpeg が見つかりません。INSTALL.md の手順で導入してください。")


def run(cmd, capture=False, check=True):
    """サブプロセス実行。capture=True で stdout+stderr を返す"""
    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    out = res.stdout.decode("utf-8", "replace") if capture and res.stdout else ""
    if check and res.returncode != 0:
        tail = "\n".join(out.splitlines()[-15:]) if out else ""
        die(f"コマンド失敗 ({res.returncode}): {' '.join(map(str, cmd))}\n{tail}")
    return out


def ffprobe_info(src):
    """回転を考慮した表示解像度・fps・尺を返す"""
    out = run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,side_data_list:format=duration",
        "-of", "json", str(src),
    ], capture=True)
    data = json.loads(out)
    st = data["streams"][0]
    w, h = int(st["width"]), int(st["height"])
    rot = 0
    for sd in st.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    if rot % 180 != 0:
        w, h = h, w
    fps = Fraction(st.get("r_frame_rate", "30/1"))
    dur = float(data["format"]["duration"])
    return {"width": w, "height": h, "fps_num": fps.numerator, "fps_den": fps.denominator,
            "fps": float(fps), "duration_s": dur, "rotation": rot}


def find_font():
    for p in FONT_CANDIDATES:
        if p.exists():
            return str(p)
    die("日本語フォントが見つかりません。assets/fonts/NotoSansCJKjp-Black.otf を確認してください。")


def find_whisper_model():
    """VIDEO_EDITING_MODEL 環境変数 → キャッシュ内の良い順"""
    env = os.environ.get("VIDEO_EDITING_MODEL")
    if env and Path(env).exists():
        return env
    order = ["large-v3-turbo", "large-v3", "medium", "small", "base"]
    if MODEL_DIR.exists():
        found = {p.name: p for p in MODEL_DIR.glob("ggml-*.bin")}
        for key in order:
            name = f"ggml-{key}.bin"
            if name in found:
                return str(found[name])
        if found:
            return str(sorted(found.values())[0])
    return None


def normalize_text(t: str) -> str:
    t = t.replace("　", "").replace(" ", "")
    return t.strip()


def apply_vocab(text: str, vocab) -> str:
    if not vocab:
        return text
    for rule in vocab.get("corrections", []):
        try:
            text = re.sub(rule["pattern"], rule["replacement"], text)
        except re.error:
            pass
    return text


def load_vocab(job):
    path = job.get("vocab")
    if not path:
        default = ASSETS / "vocabulary.json"
        path = default if default.exists() else None
    if path and Path(path).exists():
        return load_json(path)
    return None


def fmt_ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
