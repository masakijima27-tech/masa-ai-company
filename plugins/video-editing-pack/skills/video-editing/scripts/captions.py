#!/usr/bin/env python3
"""テロップの生成（1画面 = 最大2行、1行 = max_chars 文字まで）。
words_final.json（カット後タイムラインのword時刻）を、
同梱BudouXの文節境界でチャンク化 → 間（ま）・句読点・容量で画面に区切り、
2行に割るときは上下の長さバランスが最良のチャンク境界を選ぶ。
最後に語彙辞書（vocabulary.json）で誤変換を補正する。
出力: work/captions.json  {"lines":[{"text","s","e"},...]}  ※text内の改行は \n
"""
import argparse
import sys
from pathlib import Path

from common import info, load_json, save_json, load_vocab, apply_vocab, ffprobe_info

VENDOR = Path(__file__).resolve().parent / "vendor"

END_PUNCT = tuple("。？！?!」")
# 行頭に来ると不自然な語（助詞・語尾・小書き文字など）は前に残す
STICKY_WORDS = {"は", "が", "を", "に", "で", "と", "の", "も", "へ", "や", "か",
                "ね", "よ", "な", "です", "ます", "した", "ました", "される", "された"}
STICKY_HEADS = tuple("っゃゅょんーぁぃぅぇぉ、。？！?!」・…")


def is_sticky(w):
    t = w["w"]
    return t in STICKY_WORDS or t.startswith(STICKY_HEADS)


def chunkify(words, max_chars):
    """同梱のBudouX（Google製・日本語改行エンジン）で、word列を
    文節相当の自然なまとまりに再グループ化する。
    以降はチャンク単位でしか切らないので、単語の途中切れが構造的に消える。
    BudouXが読めない環境ではwhisperトークンのまま返す（品質フォールバック）。"""
    try:
        sys.path.insert(0, str(VENDOR))
        import budoux
    except Exception:
        return words, False
    chars = []
    for w in words:
        n = max(len(w["w"]), 1)
        dur = (w["e"] - w["s"]) / n
        for i, ch in enumerate(w["w"]):
            chars.append((ch, w["s"] + dur * i, w["s"] + dur * (i + 1)))
    if not chars:
        return words, False
    raw = budoux.load_default_japanese_parser().parse("".join(c[0] for c in chars))
    # 1文字だけの中途半端なチャンクは次に連結（上限は超えない）。長すぎるチャンクは強制分割
    texts = []
    for c in raw:
        if texts and len(texts[-1]) == 1 and texts[-1] not in "、。？！?!" \
                and len(texts[-1]) + len(c) <= max_chars:
            texts[-1] += c
        else:
            texts.append(c)
    texts = [c[i:i + max_chars] for c in texts for i in range(0, len(c), max_chars)]
    chunks, pos = [], 0
    for c in texts:
        seg = chars[pos:pos + len(c)]
        chunks.append({"w": c, "s": round(seg[0][1], 3), "e": round(seg[-1][2], 3)})
        pos += len(c)
    return chunks, True


def caption_of(chunks, max_chars):
    """チャンク列を1画面のテロップにする。収まらなければ2行に分割
    （両行 max_chars 以内・上下の長さ差が最小のチャンク境界を選ぶ）"""
    total = sum(len(c["w"]) for c in chunks)
    if total <= max_chars or len(chunks) == 1:
        text = "".join(c["w"] for c in chunks)
    else:
        best = None
        for i in range(1, len(chunks)):
            l1 = "".join(c["w"] for c in chunks[:i])
            l2 = "".join(c["w"] for c in chunks[i:])
            if len(l1) <= max_chars + 2 and len(l2) <= max_chars + 2 \
                    and not is_sticky(chunks[i]):
                diff = abs(len(l1) - len(l2))
                if best is None or diff < best[0]:
                    best = (diff, l1, l2)
        if best is None:  # sticky制約を外して再探索
            for i in range(1, len(chunks)):
                l1 = "".join(c["w"] for c in chunks[:i])
                l2 = "".join(c["w"] for c in chunks[i:])
                if len(l1) <= max_chars + 2 and len(l2) <= max_chars + 2:
                    diff = abs(len(l1) - len(l2))
                    if best is None or diff < best[0]:
                        best = (diff, l1, l2)
        text = f"{best[1]}\n{best[2]}" if best else "".join(c["w"] for c in chunks)
    return {"text": text, "s": chunks[0]["s"], "e": chunks[-1]["e"]}


def splittable(chunks, max_chars):
    """このチャンク列を1画面に入れたとき、1行 or 2行（両行 max_chars+2 以内）に
    収まる分割点が存在するか"""
    total = sum(len(c["w"]) for c in chunks)
    if total <= max_chars:
        return True
    acc = 0
    for c in chunks[:-1]:
        acc += len(c["w"])
        if acc <= max_chars + 2 and total - acc <= max_chars + 2:
            return True
    return False


def build_captions(units, max_chars=10, max_lines=2, gap_break=0.6, max_dur=5.0):
    capacity = max_chars * max_lines
    caps, buf = [], []
    for w in units:
        if buf:
            gap = w["s"] - buf[-1]["e"]
            cur_len = sum(len(x["w"]) for x in buf)
            over = cur_len + len(w["w"]) > capacity
            if over and is_sticky(w) and cur_len + len(w["w"]) <= capacity + 2:
                over = False
            if not over and not splittable(buf + [w], max_chars):
                over = True
            cur_dur = w["e"] - buf[0]["s"]
            if gap > gap_break or cur_dur > max_dur \
                    or buf[-1]["w"].endswith(END_PUNCT) or over:
                caps.append(caption_of(buf, max_chars))
                buf = []
        buf.append(w)
    if buf:
        caps.append(caption_of(buf, max_chars))

    # 語尾だけ等の極端に短いテロップは、前のテロップの最終行に吸収
    merged = []
    for c in caps:
        if (merged and len(c["text"]) <= 4 and "\n" not in c["text"]
                and c["s"] - merged[-1]["e"] < 0.3):
            plines = merged[-1]["text"].split("\n")
            if len(plines[-1]) + len(c["text"]) <= max_chars + 2:
                plines[-1] += c["text"]
                merged[-1]["text"] = "\n".join(plines)
                merged[-1]["e"] = c["e"]
                continue
        merged.append(c)
    return [c for c in merged if c["text"].strip("、。？！?!」「\n")]


def polish(lines, total, min_show=0.9, bridge=0.4, lead=0.2):
    """表示タイミングの調整。
    lead: テロップを声より少し先に出す（whisperの時刻は声の立ち上がりより
    遅れがちなので、先行させないと体感で「ワンテンポ遅い」になる）"""
    prev_e = 0.0
    for ln in lines:
        ln["s"] = max(prev_e, ln["s"] - lead, 0.0)
        prev_e = ln["e"]
    for i, ln in enumerate(lines):
        nxt = lines[i + 1]["s"] if i + 1 < len(lines) else total
        ln["e"] = min(ln["e"], total)
        if ln["e"] - ln["s"] < min_show:
            ln["e"] = min(ln["s"] + min_show, nxt)
        if 0 < nxt - ln["e"] < bridge:
            ln["e"] = nxt
        ln["s"], ln["e"] = round(ln["s"], 2), round(min(max(ln["e"], ln["s"] + 0.1), total), 2)
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    args = ap.parse_args()
    job = load_json(args.job)
    work = Path(job["work"])

    words = load_json(work / "words_final.json")["words"]
    total = ffprobe_info(work / "cut_final.mp4")["duration_s"]
    vocab = load_vocab(job)
    telop = job.get("telop", {})
    max_chars = int(telop.get("max_chars", 10))
    max_lines = int(telop.get("max_lines", 2))

    units, used_budoux = chunkify(words, max_chars)
    lines = build_captions(units, max_chars=max_chars, max_lines=max_lines)
    lines = polish(lines, total, lead=float(telop.get("lead_s", 0.2)))
    for ln in lines:
        ln["text"] = apply_vocab(ln["text"], vocab)

    two = sum(1 for ln in lines if "\n" in ln["text"])
    save_json(work / "captions.json", {"lines": lines, "total_s": round(total, 3)})
    info(f"テロップ生成: {len(lines)}画面（うち2行 {two} / 改行: {'BudouX' if used_budoux else '簡易'} / "
         f"語彙補正{'あり' if vocab else 'なし'}） -> {work / 'captions.json'}")


if __name__ == "__main__":
    main()
