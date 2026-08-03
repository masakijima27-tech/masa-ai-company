#!/usr/bin/env python3
"""ジャンプカット（2段階）。

stage silence: 元動画の無音・冒頭/末尾・手動DROPをカット -> cut.mp4
               ※文字起こしはこの後に行う（無音を詰めた音声の方がwhisperの時刻が正確なため）
stage filler : words.json からフィラー（えー、えっと等）を検出して2段目のカット -> cut_final.mp4
               word時刻もフィラー後タイムラインへ変換して words_final.json に保存

cut_plan.json に、元動画タイムラインでの最終keep区間（FCPXML用）も記録する。
"""
import argparse
import re
import shutil
from pathlib import Path

from common import die, info, load_json, save_json, run, ffprobe_info

FILLER_STANDARD = re.compile(r"^(えー+と?|えっと+|あー+う?|うーん+|んー+と?)$")
FILLER_STRONG = re.compile(r"^(えー+と?|えっと+|あー+う?|うーん+|んー+と?|あの+|まあ+|まぁ+|なんか)$")

ROUTE_SIZE = {"vertical": (1080, 1920), "horizontal": (1920, 1080)}


def detect_silences(src, thresh_s, noise_db=-35):
    out = run(["ffmpeg", "-hide_banner", "-i", str(src),
               "-af", f"silencedetect=noise={noise_db}dB:d={thresh_s}",
               "-f", "null", "-"], capture=True)
    silences, start = [], None
    for line in out.splitlines():
        m = re.search(r"silence_start:\s*([\d.]+)", line)
        if m:
            start = float(m.group(1))
        m = re.search(r"silence_end:\s*([\d.]+)", line)
        if m and start is not None:
            silences.append((start, float(m.group(1))))
            start = None
    if start is not None:  # 末尾まで無音
        silences.append((start, None))
    return silences


def detect_fillers(words, level):
    """連続トークンを最大3個まで結合してフィラー判定"""
    if level == "off":
        return []
    pat = FILLER_STRONG if level == "strong" else FILLER_STANDARD
    drops, i, n = [], 0, len(words)
    while i < n:
        matched = None
        for k in (3, 2, 1):
            if i + k <= n:
                joined = "".join(w["w"] for w in words[i:i + k])
                if pat.match(joined):
                    matched = k
                    break
        if matched:
            s, e = words[i]["s"], words[i + matched - 1]["e"]
            if e - s >= 0.12:
                drops.append((max(0.0, s - 0.02), e + 0.02))
            i += matched
        else:
            i += 1
    return drops


def merge_intervals(ivs):
    ivs = sorted([list(x) for x in ivs if x[1] > x[0]])
    merged = []
    for s, e in ivs:
        if merged and s <= merged[-1][1] + 0.001:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def build_keeps(duration, drops, min_keep=0.25):
    keeps, cur = [], 0.0
    for s, e in drops:
        if s > cur:
            keeps.append([cur, s])
        cur = max(cur, e)
    if cur < duration - 0.01:
        keeps.append([cur, duration])
    return [k for k in keeps if k[1] - k[0] >= min_keep]


class TimeMapper:
    """keep区間リスト -> 詰めた後のタイムライン変換"""

    def __init__(self, keeps):
        self.keeps = keeps
        self.offsets = []
        acc = 0.0
        for s, e in keeps:
            self.offsets.append(acc)
            acc += e - s
        self.total = acc

    def contains(self, t):
        return any(s - 0.001 <= t <= e + 0.001 for s, e in self.keeps)

    def map_clamp(self, t):
        prev_end = 0.0
        for (s, e), off in zip(self.keeps, self.offsets):
            if t < s:
                return prev_end
            if t <= e:
                return off + (t - s)
            prev_end = off + (e - s)
        return self.total

    def to_source(self, keeps2):
        """このマッパーのカット後タイムライン上の区間group -> 元タイムラインの区間group"""
        out = []
        for a, b in keeps2:
            for (s, e), off in zip(self.keeps, self.offsets):
                length = e - s
                lo, hi = max(a, off), min(b, off + length)
                if hi - lo > 0.01:
                    out.append([s + (lo - off), s + (hi - off)])
        return merge_intervals(out)


def scale_filter(src_w, src_h, tw, th):
    """クロップtoフィル（リール標準）: 足りない方向を切ってピッタリ合わせる"""
    src_ar = src_w / src_h
    tgt_ar = tw / th
    if abs(src_ar - tgt_ar) < 0.01:
        return f"scale={tw}:{th}:flags=lanczos"
    if src_ar > tgt_ar:  # 横に長い → 左右をクロップ
        return f"crop=ih*{tw}/{th}:ih,scale={tw}:{th}:flags=lanczos"
    return f"crop=iw:iw*{th}/{tw},scale={tw}:{th}:flags=lanczos"


def apply_cuts(src, keeps, out, vf=None, fps=None, preset="veryfast", crf=18):
    parts, concat = [], ""
    for i, (s, e) in enumerate(keeps):
        parts.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}];"
                     f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}];")
        concat += f"[v{i}][a{i}]"
    fc = "".join(parts) + f"{concat}concat=n={len(keeps)}:v=1:a=1[vc][ac]"
    if vf:
        fc += f";[vc]{vf},fps={fps}[vo]"
        vmap = "[vo]"
    else:
        vmap = "[vc]"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
         "-filter_complex", fc, "-map", vmap, "-map", "[ac]",
         "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         str(out)])


def stage_silence(job, job_path, work):
    src = job["src"]
    cut = job.get("cut", {})
    probe = job.get("src_info") or ffprobe_info(src)
    duration = probe["duration_s"]
    pad = float(cut.get("pad_s", 0.15))
    thresh = float(cut.get("silence_s", 1.0))

    drops = []
    for s, e in detect_silences(src, thresh):
        e = duration if e is None else e
        s2, e2 = s + pad, e - pad
        if e2 > s2:
            drops.append((s2, e2))
    head, tail = float(cut.get("head_s", 0)), float(cut.get("tail_s", 0))
    if head > 0:
        drops.append((0.0, head))
    if tail > 0:
        drops.append((duration - tail, duration))
    for d in cut.get("drops", []):
        drops.append((float(d[0]), float(d[1])))

    keeps = build_keeps(duration, merge_intervals(drops))
    if not keeps:
        die("keep区間がゼロです。カット条件が強すぎます（無音閾値やDROP範囲を見直してください）。")
    kept = sum(e - s for s, e in keeps)
    info(f"無音カット計画: {duration:.1f}s -> {kept:.1f}s（{duration - kept:.1f}s 削除 / {len(keeps)}区間）")

    tw, th = ROUTE_SIZE.get(job.get("route", "vertical"), ROUTE_SIZE["vertical"])
    vf = scale_filter(probe["width"], probe["height"], tw, th)
    fps = f"{min(probe.get('fps', 30) or 30, 60):.6g}"
    enc = job.get("encode", {})
    info(f"無音カット適用中... ({tw}x{th})")
    apply_cuts(src, keeps, work / "cut.mp4", vf=vf, fps=fps,
               preset=enc.get("preset", "veryfast"), crf=int(enc.get("crf", 18)))

    plan = {
        "src_duration_s": round(duration, 3),
        "stage1_keeps_src": [[round(s, 3), round(e, 3)] for s, e in keeps],
        "stage1_duration_s": round(kept, 3),
        "keeps_src_final": [[round(s, 3), round(e, 3)] for s, e in keeps],
        "final_duration_s": round(kept, 3),
        "fillers_cut": [],
    }
    save_json(work / "cut_plan.json", plan)
    info(f"無音カット完了 -> {work / 'cut.mp4'}")


def stage_filler(job, job_path, work):
    plan = load_json(work / "cut_plan.json")
    words = load_json(work / "words.json")["words"]
    level = job.get("cut", {}).get("filler", "standard")
    cut1 = work / "cut.mp4"
    dur1 = plan["stage1_duration_s"]

    fillers = detect_fillers(words, level)
    if not fillers:
        info("フィラー検出: 0箇所（2段目カットなし）")
        shutil.copy2(cut1, work / "cut_final.mp4")
        save_json(work / "words_final.json", {"words": words})
        return

    drops = merge_intervals(fillers)
    keeps2 = build_keeps(dur1, drops, min_keep=0.15)
    mapper2 = TimeMapper(keeps2)

    # word時刻をフィラー後タイムラインへ
    out_words = []
    for w in words:
        mid = (w["s"] + w["e"]) / 2
        if not mapper2.contains(mid):
            continue
        s = mapper2.map_clamp(w["s"])
        e = max(mapper2.map_clamp(w["e"]), s + 0.02)
        out_words.append({"w": w["w"], "s": round(s, 3), "e": round(e, 3)})

    info(f"フィラー検出: {len(fillers)}箇所（{sum(e - s for s, e in drops):.1f}s）を2段目カット")
    enc = job.get("encode", {})
    apply_cuts(cut1, keeps2, work / "cut_final.mp4",
               preset=enc.get("preset", "veryfast"), crf=int(enc.get("crf", 18)))
    save_json(work / "words_final.json", {"words": out_words})

    # 元動画タイムラインでの最終keep（FCPXML用）
    mapper1 = TimeMapper(plan["stage1_keeps_src"])
    plan["fillers_cut"] = [[round(s, 3), round(e, 3)] for s, e in drops]
    plan["keeps_src_final"] = [[round(s, 3), round(e, 3)] for s, e in mapper1.to_source(keeps2)]
    plan["final_duration_s"] = round(mapper2.total, 3)
    save_json(work / "cut_plan.json", plan)
    info(f"フィラーカット完了 -> {work / 'cut_final.mp4'}（最終 {mapper2.total:.1f}s）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--stage", required=True, choices=["silence", "filler"])
    args = ap.parse_args()
    job = load_json(args.job)
    work = Path(job["work"])
    if args.stage == "silence":
        stage_silence(job, args.job, work)
    else:
        stage_filler(job, args.job, work)


if __name__ == "__main__":
    main()
