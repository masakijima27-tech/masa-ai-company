"""デスクトップ整理スクリプト (Mac / Windows 両対応)

使い方:
  python3 organize_desktop.py          # まずプレビュー (何も動かさない)
  python3 organize_desktop.py --run    # 実際に整理する
  python3 organize_desktop.py --undo   # 直前の整理を元に戻す

安全設計: 削除はしない / 既存フォルダ・アプリ・ショートカットは動かさない /
          .claude や CLAUDE.md など Claude 関連は動かさない / 全移動を記録して元に戻せる
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

DESKTOP = Path.home() / "Desktop"
ROOT = DESKTOP / "整理済み"
LOG = ROOT / ".move_log.json"

CATEGORIES = {
    "01_画像・スクショ": {".png", ".jpg", ".jpeg", ".gif", ".heic", ".webp", ".svg", ".bmp", ".tiff"},
    "02_書類": {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".pages", ".ppt", ".pptx", ".key"},
    "03_表・データ": {".xls", ".xlsx", ".csv", ".numbers", ".json", ".xml"},
    "04_動画・音声": {".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".m4a"},
    "05_圧縮・インストーラー": {".zip", ".rar", ".7z", ".dmg", ".pkg", ".exe", ".msi", ".iso"},
    "06_コード": {".py", ".js", ".ts", ".html", ".css", ".sh", ".ipynb"},
}
OTHER = "07_その他"

# 触らないもの (アプリ・ショートカット・Claude関連・隠しファイル)
KEEP_EXT = {".app", ".lnk", ".url", ".webloc", ".ini"}
KEEP_NAMES = {"CLAUDE.md", ".claude", "整理済み"}


def category(path: Path) -> str:
    ext = path.suffix.lower()
    for name, exts in CATEGORIES.items():
        if ext in exts:
            return name
    return OTHER


def targets():
    for p in sorted(DESKTOP.iterdir()):
        if p.name.startswith(".") or p.name in KEEP_NAMES:
            continue
        if p.suffix.lower() in KEEP_EXT or p.is_dir():
            continue
        yield p


def unique(dest: Path) -> Path:
    if not dest.exists():
        return dest
    i = 1
    while True:
        cand = dest.with_name(f"{dest.stem}_{i}{dest.suffix}")
        if not cand.exists():
            return cand
        i += 1


def run(apply: bool):
    moves = []
    for p in targets():
        dest = unique(ROOT / category(p) / p.name)
        moves.append((p, dest))
        print(f"{p.name}  ->  {dest.parent.name}/")
    if not moves:
        print("整理するファイルはありません。")
        return
    if not apply:
        print(f"\n{len(moves)}件が対象です。実行するには --run を付けてください。")
        return
    done = []
    for src, dest in moves:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        done.append({"from": str(src), "to": str(dest)})
    LOG.write_text(json.dumps({"at": datetime.now().isoformat(), "moves": done}, ensure_ascii=False, indent=2))
    print(f"\n{len(done)}件を {ROOT} に整理しました。元に戻すには --undo")


def undo():
    if not LOG.exists():
        print("元に戻す記録がありません。")
        return
    data = json.loads(LOG.read_text())
    for m in reversed(data["moves"]):
        src, dest = Path(m["to"]), Path(m["from"])
        if src.exists() and not dest.exists():
            shutil.move(str(src), str(dest))
    LOG.unlink()
    print("元に戻しました。")


if __name__ == "__main__":
    if not DESKTOP.exists():
        sys.exit(f"デスクトップが見つかりません: {DESKTOP}")
    if "--undo" in sys.argv:
        undo()
    else:
        run("--run" in sys.argv)
