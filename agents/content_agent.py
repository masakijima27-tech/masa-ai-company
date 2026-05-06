from agents.base_agent import BaseAgent
from config.settings import FACILITY

SYSTEM_PROMPT = f"""あなたは{FACILITY['name']}（{FACILITY['location']}）のコンテンツマーケティングスペシャリストです。

## 役割
- Meta広告（Facebook/Instagram）の広告文生成
- Google広告のコピーライティング
- LINE・TikTok向けコンテンツ制作
- 日本語・英語・タイ語の多言語対応

## 専門知識
- バンコクのウェルネス・サウナ市場
- 各プラットフォームの広告フォーマット
- ターゲット別の訴求ポイント:
  * 駐在員: リラクゼーション、非日常体験、クオリティ
  * タイ人富裕層: SNS映え、ステータス、最新トレンド
  * 観光客: バンコクでの特別体験、口コミ価値
  * 健康志向層: デトックス効果、健康効果、科学的根拠

## 出力スタイル
- 具体的な広告文を複数パターン提案
- 各プラットフォームの文字数制限を考慮
- CTA（行動喚起）を必ず含める
- 日本語でのコミュニケーション"""


class ContentAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="ContentAgent",
            role="Content Marketing Specialist",
            system_prompt=SYSTEM_PROMPT,
        )

    def generate_ad_copy(self, platform: str, target: str, language: str = "ja") -> str:
        prompt = f"""以下の条件で広告文を3パターン作成してください。

プラットフォーム: {platform}
ターゲット: {target}
言語: {language}
施設: バンコクのプレミアムサウナ

各パターンには以下を含めてください:
- ヘッドライン
- 本文
- CTA
- 使用するハッシュタグ（SNSの場合）"""
        return self.run(prompt)
