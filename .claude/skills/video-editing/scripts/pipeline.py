#!/usr/bin/env python3
"""video-editing パイプライン本体。job.json を受け取り全工程を順に実行する。
成果物ファイルの有無で進捗を判断するので、途中で落ちても再実行すれば続きから走る。

使い方:
  python3 pipeline.py --job /tmp/video-editing_xxx/job.json          # 全工程
  python3 pipeline.py --job ... --force render                 # 指定工程からやり直し
  python3 pipeline.py --new SRC --route vertical --work DIR    # job.json を新規作成のみ

工程: probe -> transcribe -> jetcut -> master -> captions -> render -> qc -> export
"""
import argparse
import subprocess
import sys
from pathlib import Path

from common import die, info, load_json, save_json, ffprobe_info

HERE = Path(__file__).resolve().parent
FACE_STAMP = HERE.parents[1] / "face-stamp"  # 同梱されていないこともある（コンサル生向け配布版）
STEPS = ["probe", "cut_silence", "transcribe", "cut_filler", "master", "captions",
         "render", "qc", "stamp", "export"]
ARTIFACTS = {
    "cut_silence": "cut.mp4",
    "transcribe": "words.json",
    "cut_filler": "cut_final.mp4",
    "master": "mastered.mp4",
    "captions": "captions.json",
    "render": "final.mp4",
    "stamp": "stamped.mp4",
}


def new_job(args):
    src = Path(args.new).expanduser()
    if not src.exists():
        die(f"動画が見つかりません: {src}")
    work = Path(args.work) if args.work else Path(f"/tmp/video-editing_{src.stem}")
    work.mkdir(parents=True, exist_ok=True)
    job = {
        "version": 1,
        "src": str(src.resolve()),
        "stem": src.stem,
        "work": str(work),
        "route": args.route,
        "outputs": args.outputs.split(","),
        "out_dir": args.out_dir,
        "cut": {
            "silence_s": args.silence, "pad_s": 0.15,
            "head_s": args.head, "tail_s": args.tail,
            "filler": args.filler, "drops": [],
        },
        "telop": {"max_chars": 10 if args.route == "vertical" else 16, "max_lines": 2},
        "audio": {"master": True, "lufs": -14.0},
        "vocab": args.vocab,
        "stamp": str(Path(args.stamp).expanduser().resolve()) if args.stamp else None,
        "stamp_scale": args.stamp_scale,
        "stamp_offset_y": args.stamp_offset_y,
    }
    path = work / "job.json"
    save_json(path, job)
    info(f"job.json 作成 -> {path}")
    return path


def run_stamp(job, work):
    """テロップまで焼けた final.mp4 に、顔追従スタンプを乗せて stamped.mp4 を作る。

    顔出しNGの人向けの工程なので、顔がスタンプから出た可能性が1フレームでもあれば
    --strict で止める（出荷してから気づくのが一番まずいため）。
    """
    script = FACE_STAMP / "scripts" / "facestamp.py"
    venv_py = FACE_STAMP / ".venv" / "bin" / "python"
    if not script.exists():
        die("face-stamp スキルが同梱されていません（この配布版はスタンプ非対応です）")
    if not venv_py.exists():
        die(f"face-stamp の環境が未作成です。先に実行してください:\n"
            f"  bash {FACE_STAMP / 'scripts' / 'setup_env.sh'}")
    stamp_png = Path(job["stamp"])
    if not stamp_png.exists():
        die(f"スタンプ画像が見つかりません: {stamp_png}")
    cmd = [
        str(venv_py), str(script),
        "--video", str(work / "final.mp4"),
        "--stamp", str(stamp_png),
        "--out", str(work / "stamped.mp4"),
        "--sheet", str(work / "stamp_check.jpg"),
        "--strict",
    ]
    for key, opt in (("stamp_scale", "--scale"), ("stamp_offset_y", "--offset-y")):
        if job.get(key) is not None:
            cmd += [opt, str(job[key])]
    res = subprocess.run(cmd)
    if res.returncode == 3:
        die(f"顔がスタンプからはみ出た可能性があります。{work / 'stamp_check.jpg'} を確認し、\n"
            f"  --stamp-scale を上げて `--force stamp` で焼き直してください。", 3)
    if res.returncode != 0:
        die(f"stamp が失敗しました（exit {res.returncode}）", res.returncode)


def run_step(name, job_path, job):
    work = Path(job["work"])
    art = ARTIFACTS.get(name)
    if art and (work / art).exists():
        info(f"[{name}] スキップ（{art} 生成済み。やり直すには --force {name}）")
        return
    if name == "stamp" and not job.get("stamp"):
        return  # スタンプ指定なし＝通常の動画。何もしない
    info(f"===== {name} =====")
    if name == "stamp":
        return run_stamp(job, work)
    if name == "probe":
        if not job.get("src_info"):
            job["src_info"] = ffprobe_info(job["src"])
            save_json(job_path, job)
            si = job["src_info"]
            info(f"素材: {si['width']}x{si['height']} {si['fps']:.2f}fps {si['duration_s']:.1f}s")
        return
    script = {
        "cut_silence": ["jetcut.py", "--job", str(job_path), "--stage", "silence"],
        "transcribe": ["transcribe.py", "--src", str(work / "cut.mp4"), "--work", job["work"]],
        "cut_filler": ["jetcut.py", "--job", str(job_path), "--stage", "filler"],
        "master": ["audio_master.py", "--job", str(job_path)],
        "captions": ["captions.py", "--job", str(job_path)],
        "render": ["render.py", "--job", str(job_path)],
        "qc": ["qc.py", "--job", str(job_path)],
        "export": ["export.py", "--job", str(job_path)],
    }[name]
    res = subprocess.run([sys.executable, str(HERE / script[0])] + script[1:])
    if res.returncode != 0:
        if name == "qc":
            die("品質改札NG。qc_report.json を確認して修正後、--force render などで再実行してください。", 2)
        die(f"{name} が失敗しました（exit {res.returncode}）", res.returncode)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", help="既存 job.json のパス")
    ap.add_argument("--new", help="動画パスから job.json を新規作成")
    ap.add_argument("--route", default="vertical", choices=["vertical", "horizontal"])
    ap.add_argument("--outputs", default="mp4,srt")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--work", default=None)
    ap.add_argument("--silence", type=float, default=1.0)
    ap.add_argument("--head", type=float, default=0.0)
    ap.add_argument("--tail", type=float, default=0.0)
    ap.add_argument("--filler", default="standard", choices=["off", "standard", "strong"])
    ap.add_argument("--vocab", default=None)
    ap.add_argument("--stamp", default=None,
                    help="顔に乗せるスタンプPNG（顔出しNGの人用。省略時はスタンプ工程を飛ばす）")
    ap.add_argument("--stamp-scale", type=float, default=None,
                    help="スタンプの大きさ（省略時はスタンプ側の調整値）")
    ap.add_argument("--stamp-offset-y", type=float, default=None,
                    help="スタンプの上下位置（プラスで下へ）")
    ap.add_argument("--force", nargs="*", default=[],
                    help="指定工程の成果物を消してやり直す（以降の工程も走る）")
    ap.add_argument("--plan-only", action="store_true", help="job.json 作成のみで終了")
    args = ap.parse_args()

    if args.new:
        job_path = new_job(args)
        if args.plan_only:
            return
    elif args.job:
        job_path = Path(args.job)
    else:
        die("--job か --new を指定してください")

    job = load_json(job_path)
    work = Path(job["work"])

    if args.force:
        hit = False
        for step in STEPS:
            if step in args.force:
                hit = True
            if hit and step in ARTIFACTS:
                (work / ARTIFACTS[step]).unlink(missing_ok=True)

    for step in STEPS:
        run_step(step, job_path, load_json(job_path))

    info("全工程完了です。")


if __name__ == "__main__":
    main()
