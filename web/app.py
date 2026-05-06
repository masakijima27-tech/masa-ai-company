import sys
import json
import re
sys.path.insert(0, '/home/user/masa-ai-company')

from flask import Flask, render_template, request, jsonify
from agents.content_agent import ContentAgent

app = Flask(__name__)
content_agent = ContentAgent()

PLATFORM_ICONS = {
    "Instagram": "📸", "Facebook": "🔵", "Google広告": "🔍",
    "LINE": "💬", "TikTok": "🎵", "Meta広告（Instagram/Facebook）": "📸",
}
LANG_LABELS = {"ja": "日本語", "en": "英語", "th": "タイ語"}
LANG_CLASS = {"ja": "ja", "en": "en", "th": "th"}

# Pre-generated content from our session
INITIAL_ADS = [
    {
        "icon": "📸",
        "platform": "Instagram",
        "target": "日本人駐在員",
        "lang": "ja",
        "lang_label": "日本語",
        "headline": "バンコクで、本物の『ととのい』を。",
        "preview": "忙しい駐在生活の中で、自分だけの時間、持てていますか？",
        "pattern_count": 3,
        "cta_type": "予約促進",
        "patterns": [
            {
                "title": "「非日常の逃げ場」訴求",
                "headline": "バンコクで、本物の“ととのい”を。",
                "body": "忙しい駐在生活の中で、\n自分だけの時間、持てていますか？\n\nMASA SAUNAは、\nバンコクの喧騒から切り離された\n完全プレミアムサウナ空間。\n\n🌿 フィンランド式本格ロウリュ\n🌿 プライベート個室完備\n🌿 日本語スタッフ常駐\n\n「ここに来ると、やっと息ができる気がする」\n―在住3年目、Kさん\n\n今週末、自分へのご褒美を。",
                "cta": "▶ プロフィールのリンクから今すぐ予約\n初回限定 20%OFF キャンペーン実施中",
                "hashtags": ["#バンコク駐在", "#バンコクサウナ", "#ととのう", "#MASASauna", "#バンコク生活", "#駐在員の休日", "#Bangkoksauna", "#プレミアムサウナ"]
            },
            {
                "title": "「クオリティ・本物志向」訴求",
                "headline": "妥協しない人のための、サウナがある。",
                "body": "タイに来ても、クオリティは落としたくない。\n\nそんなあなたへ——\n\n✅ 室温・湿度を徹底管理した本格ストーブ\n✅ 天然白樺ヴィヒタによる本場のロウリュ\n✅ 水風呂 × 外気浴の黄金サイクルを完全再現\n\n「日本のサウナと比べても、ここは別格」\n多くの駐在員の方に選ばれ続けています。",
                "cta": "▶ ストーリーズのリンクをタップ\n週末・平日ともに予約受付中｜日本語OK",
                "hashtags": ["#MASA_SAUNA", "#バンコクサウナ", "#サウナー", "#ととのい", "#バンコク駐在員", "#プレミアムサウナ", "#ロウリュ"]
            },
            {
                "title": "「疲労回復・健康効果」訴求",
                "headline": "その疲れ、バンコクで溶かしてきませんか？",
                "body": "駐在員の8割が感じている、\n「タイの気候と仕事のダブル疲労」。\n\nMASA SAUNAの90分が、\n1週間分の疲れをリセットします。\n\n🔥 高温サウナで深部体温UP\n💧 冷水浴で自律神経を整える\n😌 外気浴で究極のリラックス状態へ\n\n毎週通う駐在員続出中——\nあなたの“週次メンテナンス”に、ぜひ。",
                "cta": "▶ プロフィールリンクから体験予約\n💬 DMでのご質問も日本語で対応します",
                "hashtags": ["#バンコクサウナ", "#サウナ効果", "#ととのう", "#MASASauna", "#駐在員生活", "#自律神経", "#デトックス"]
            }
        ]
    },
    {
        "icon": "📸",
        "platform": "Instagram",
        "target": "タイ人富裕層",
        "lang": "th",
        "lang_label": "タイ語",
        "headline": "สัมผัสประสบการณ์ที่ไม่เหมือนใคร",
        "preview": "ไม่ใช่แค่ซาวน่า... แต่คือ Ritual ของคนที่รู้จักคุณค่าของตัวเอง",
        "pattern_count": 3,
        "cta_type": "予約促進",
        "patterns": [
            {
                "title": "ステータス・エクスクルーシブ訴求",
                "headline": "สัมผัสประสบการณ์ที่ไม่เหมือนใคร\nในโลกของ MASA SAUNA",
                "body": "ไม่ใช่แค่ซาวน่า...\nแต่คือ Ritual ของคนที่รู้จักคุณค่าของตัวเอง ✨\n\n🏯 บรรยากาศสไตล์ญี่ปุ่นพรีเมียม\n🌿 อุณหภูมิที่ผ่านการคัดสรรมาอย่างพิถีพิถัน\n🥂 เพราะการดูแลตัวเองคือ Luxury ที่คุณสมควรได้รับทุกวัน\n\nใจกลาง Thonglor — เดินทางง่าย เหมาะกับทุก Lifestyle",
                "cta": "📲 จองเลย — Slot พิเศษสำหรับสัปดาห์นี้มีจำนวนจำกัด\n👉 จองออนไลน์ / ดูแพ็กเกจ",
                "hashtags": ["#MASASauna", "#LuxuryWellness", "#SaunaBangkok", "#Thonglor", "#พรีเมียมซาวน่า", "#BangkokLuxury"]
            },
            {
                "title": "ウェルネス・健康効果訴求",
                "headline": "Reset ร่างกาย รีเซ็ตจิตใจ\nใน 60 นาที กับ MASA SAUNA",
                "body": "เราทุกคนรู้ว่า...\nชีวิตในเมืองมัน \"หนัก\" แค่ไหน 😮‍💨\n\n✅ ลดความเครียดสะสม\n✅ ผิวกระจ่างใส จากการ Detox ระดับเซลล์\n✅ นอนหลับดีขึ้น หลังเข้าใช้บริการ\n✅ ระบบ Circulation ดีขึ้นอย่างเห็นได้ชัด\n\nเพราะ Wellness ที่ดีต้องเริ่มจากข้างใน 🌸",
                "cta": "🌿 ทดลองใช้ครั้งแรก — Special Intro Price\n👉 ดูโปรโมชั่น / Line: @MASASauna",
                "hashtags": ["#MASASauna", "#WellnessBangkok", "#Detox", "#InnerBeauty", "#สุขภาพดี", "#ซาวน่าบางกอก"]
            },
            {
                "title": "SNS映え・ライフスタイル訴求",
                "headline": "Aesthetic ที่สุด\nซาวน่าที่คุณอยากมาซ้ำ ❤️‍🔥",
                "body": "ถ้า Feed ของคุณสะท้อน Lifestyle ของคุณ...\n\nMASA SAUNA คือ Chapter ที่คุณต้องมี 📖✨\n\n🏮 Interior สไตล์ Japanese Minimalist\n🔥 Sauna Experience ที่ไม่มีที่ไหนในกรุงเทพฯ\n🧖‍♀️ Private Room สำหรับกลุ่มเพื่อน\n\nใครเป็น Sauna Girl บ้าง? 🙋‍♀️\nTag เพื่อนที่ต้องพามาเลย!",
                "cta": "📍 Thonglor, Bangkok\n📲 จองผ่าน DM หรือ Link in Bio\n🎁 มาเป็นกลุ่ม 3 คนขึ้นไป รับส่วนลดพิเศษ!",
                "hashtags": ["#MASASauna", "#SaunaGirl", "#BangkokAesthetic", "#ThonlorVibes", "#ซาวน่า", "#LuxuryLife", "#สายสุขภาพ"]
            }
        ]
    }
]

CAMPAIGN_TEXT = """キャンペーン設計書 — MASA SAUNA バンコク
予算: 50,000 THB / 月　｜　期間: 30日間　｜　目標: 新規顧客獲得150件

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
予算配分

META広告計          28,000 THB (56%)
├─ 日本人駐在員        6,000 THB → 目標30件
├─ 欧米系駐在員        4,000 THB → 目標18件
├─ タイ人富裕層       10,000 THB → 目標40件
└─ 観光客              8,000 THB → 目標32件

GOOGLE広告計         18,000 THB (36%)
├─ 検索広告（日/英/タイ） 12,000 THB → 目標25件
└─ ディスプレイ・リターゲ  6,000 THB → 目標5件

制作・運用費          4,000 THB (8%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4週間スケジュール

Week 1 | 認知フェーズ（12,500 THB）
  Day 1-2: テクニカル基盤整備・ピクセル設置
  Day 3-5: 素材入稿・審査対応
  Day 6-7: テスト配信・トラッキング確認

Week 2 | フルローンチ（17,500 THB）
  Day 8:   全キャンペーン本予算で稼働
  Day 8-14: 日次モニタリング（CPC・CTR・予約数）
  Day 14:  中間レポート・予算調整判断

Week 3 | 最適化フェーズ（15,000 THB）
  Day 15-16: 高CTRセグメントへ予算シフト
  Day 17-18: リターゲティング本格化
  Day 19-20: カート離脱ユーザーへのプッシュ

Week 4 | 定着フェーズ（5,000 THB）
  Day 22-25: 高CVRセグメントに集中
  Day 26-28: 来店済み顧客への紹介キャンペーン
  Day 29-30: 最終レポート・次月設計

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KPI目標

新規予約数: 150件/月
CPA目標:   ≤ 333 THB
ROAS:      ≥ 3.0倍
CTR(Meta): ≥ 1.5%
CTR(Google検索): ≥ 5%
"""


def parse_ad_response(raw: str, platform: str, target: str, lang: str) -> dict:
    """Agent出力を構造化データに変換する簡易パーサー"""
    icon = PLATFORM_ICONS.get(platform, "📢")
    lang_label = LANG_LABELS.get(lang, lang)

    # ヘッドラインを抽出（最初のパターンの最初の見出し行）
    lines = [l.strip() for l in raw.split('\n') if l.strip()]
    headline = next((l for l in lines if len(l) > 5 and not l.startswith('#') and not l.startswith('Pattern') and not l.startswith('パターン') and not l.startswith('---')), platform + " 広告")

    # 3パターンに分割（簡易）
    patterns = []
    segments = re.split(r'(?:Pattern\s*[A-C123]|パターン\s*[A-C123])', raw, flags=re.IGNORECASE)
    for i, seg in enumerate(segments[1:4], 1):
        seg_lines = seg.strip().split('\n')
        title_line = seg_lines[0].strip().lstrip('|｜「』').strip() if seg_lines else f"パターン {i}"
        pat_headline = ""
        pat_body = ""
        pat_cta = ""
        pat_tags = []

        in_body = False
        for line in seg_lines[1:]:
            l = line.strip()
            if not l:
                continue
            if any(k in l for k in ['ヘッドライン', 'Headline', 'หัวข้อ']):
                in_body = False; continue
            if any(k in l for k in ['本文', 'Body', 'เนื้อหา']):
                in_body = True; continue
            if any(k in l for k in ['CTA', 'cta']):
                in_body = False; continue
            if l.startswith('#') or l.startswith('＃'):
                pat_tags = [t.strip() for t in l.split() if t.startswith('#') or t.startswith('＃')]
                continue
            if not pat_headline:
                pat_headline = l
            elif in_body:
                pat_body += l + '\n'
            elif pat_headline and not pat_cta and len(l) < 80:
                pat_cta = l

        patterns.append({
            "title": title_line[:40],
            "headline": pat_headline or f"パターン {i}",
            "body": pat_body.strip() or seg[:200],
            "cta": pat_cta or "今すぐ予約",
            "hashtags": pat_tags,
        })

    if not patterns:
        patterns = [{"title": "生成コンテンツ", "headline": headline, "body": raw[:500], "cta": "今すぐ予約", "hashtags": []}]

    return {
        "icon": icon,
        "platform": platform,
        "target": target,
        "lang": lang,
        "lang_label": lang_label,
        "headline": patterns[0]["headline"] if patterns else headline,
        "preview": (patterns[0]["body"][:80] + "…") if patterns else "",
        "pattern_count": len(patterns),
        "cta_type": "予約促進",
        "patterns": patterns,
    }


@app.route('/')
def index():
    return render_template(
        'index.html',
        ads=INITIAL_ADS,
        ads_json=json.dumps(INITIAL_ADS, ensure_ascii=False),
        campaign_text=CAMPAIGN_TEXT,
    )


@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    platform = data.get('platform', 'Instagram')
    target = data.get('target', '日本人駐在員')
    lang = data.get('lang', 'ja')

    try:
        raw = content_agent.generate_ad_copy(platform, target, lang)
        item = parse_ad_response(raw, platform, target, lang)
        return jsonify({"item": item})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860, debug=False)
