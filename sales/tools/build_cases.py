"""case_data.py から 07_営業案件リスト.md と共有ページ(HTML)を生成する。
使い方: python3 sales/tools/build_cases.py [HTML出力先]
"""
import html, json, sys
from pathlib import Path
from case_data import CASES, REWARD

ROOT = Path(__file__).resolve().parent.parent


def yen(n):
    return f"{n:,}円"


def man(lo, hi):
    f = lambda v: f"{v/10000:g}万" if v >= 10000 else f"{v:,}円"
    return f"{f(lo)}〜{f(hi)}"


def rewards(price, monthly):
    r = REWARD
    if monthly:
        i = max(r["min_reward"], int(round(price * r["monthly_intro_rate"], -2)))
        c = max(r["min_reward"], int(round(price * r["monthly_close_rate"], -2)))
        m = r["monthly_months"]
        return i, c, f"紹介 月{yen(i)}／成約 月{yen(c)}（{m}ヶ月）", c * m
    i = max(r["min_reward"], int(round(price * r["intro_rate"], -2)))
    c = max(r["min_reward"], int(round(price * r["close_rate"], -2)))
    return i, c, f"紹介 {yen(i)}／成約 {yen(c)}", c


rows = []
for cat, name, scope, market, ai, ours, unit, days, monthly in CASES:
    mid = (market[0] + market[1]) / 2
    ratio = round(ours / mid * 100)
    i, c, label, total = rewards(ours, monthly)
    rows.append(dict(cat=cat, name=name, scope=scope, market=man(*market), ai=man(*ai),
                     ours=ours, unit=unit, days=days, monthly=monthly, ratio=ratio,
                     intro=i, close=c, reward=label, total=total))

# ---- Markdown ----
md = ["# 営業案件リスト（全サービス・価格・作業範囲・営業報酬）", "",
      "> `tools/case_data.py` から自動生成。価格を変えるときはデータを直して `python3 sales/tools/build_cases.py` を実行。",
      "> 金額は税別・2026年時点の国内相場の目安。【要調整：自社の原価と実績で最終確定】", "",
      "**列の見方**",
      "- 一般相場：従来の制作会社・開発会社の価格帯",
      "- AI会社相場：AI活用をうたう受託会社・フリーランスの価格帯",
      "- 当社価格：営業が提示する標準価格（ここから値引きは最大10%まで）",
      "- 相場比：当社価格 ÷ 一般相場の中央値。**40〜70%が勝てるゾーン**",
      f"- 営業報酬：紹介のみ {int(REWARD['intro_rate']*100)}%／成約まで {int(REWARD['close_rate']*100)}%。月額は紹介 {int(REWARD['monthly_intro_rate']*100)}%・成約 {int(REWARD['monthly_close_rate']*100)}% を{REWARD['monthly_months']}ヶ月", ""]
cur = None
for r in rows:
    if r["cat"] != cur:
        cur = r["cat"]
        md += ["", f"## {cur}", "",
               "| 案件 | 当社がやる範囲 | 一般相場 | AI会社相場 | **当社価格** | 相場比 | 納期 | 営業報酬 |",
               "|---|---|---|---|---|---|---|---|"]
    md.append(f"| {r['name']} | {r['scope']} | {r['market']} | {r['ai']} | **{yen(r['ours'])}／{r['unit']}** | {r['ratio']}% | {r['days']} | {r['reward']} |")
md += ["", "## 共通ルール",
       "- 支払い：着手金50%・納品時50%（月額は月末請求）",
       "- 修正：記載回数まで無料。それ以上は1回あたり価格の10%",
       "- 範囲外の作業は別見積。営業が独断で「全部込み」と言わない",
       "- 「〜」のついた案件（システム・アプリ・SaaS）は最低価格。要件次第で上がる＝報酬も上がる", ""]
(ROOT / "07_営業案件リスト.md").write_text("\n".join(md), encoding="utf-8")

# ---- HTML ----
if len(sys.argv) > 1:
    tpl = (ROOT / "tools" / "page_template.html").read_text(encoding="utf-8")
    out = tpl.replace("/*__CASES__*/[]", json.dumps(rows, ensure_ascii=False))
    Path(sys.argv[1]).write_text(out, encoding="utf-8")
print(f"{len(rows)} cases written")
