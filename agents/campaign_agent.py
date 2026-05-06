from agents.base_agent import BaseAgent
from config.settings import FACILITY

SYSTEM_PROMPT = f"""あなたは{FACILITY['name']}（{FACILITY['location']}）のキャンペーンマネージャーです。

## 役割
- 広告キャンペーンの企画・設計
- 予算配分と入札戦略の提案
- キャンペーンスケジュール管理
- ROI・効果測定指標の設定

## 専門知識
- Meta広告（Facebook/Instagram）キャンペーン設計
- Google広告（検索・ディスプレイ）
- LINE広告（タイ市場向け）
- TikTok広告
- バンコク市場の競合環境
- タイの祝日・観光シーズン

## キャンペーン設計の原則
- フェーズ別アプローチ（認知→集客→リピーター）
- A/Bテストの組み込み
- 予算効率を最優先
- タイ語・英語・日本語の使い分け

## 出力スタイル
- 具体的な数値（予算、期間、KPI）を含める
- 実行可能なアクションプランを提示
- 日本語でのコミュニケーション"""


class CampaignAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CampaignAgent",
            role="Campaign Manager",
            system_prompt=SYSTEM_PROMPT,
        )

    def design_campaign(self, objective: str, budget_thb: int, duration_days: int) -> str:
        prompt = f"""以下の条件でキャンペーンを設計してください。

目的: {objective}
予算: {budget_thb:,} バーツ
期間: {duration_days} 日間
施設: バンコクのプレミアムサウナ

以下を含む詳細なキャンペーンプランを作成してください:
1. キャンペーン概要・目標
2. チャネル別予算配分
3. ターゲティング設定
4. 週次スケジュール
5. KPI・成功指標
6. A/Bテスト計画"""
        return self.run(prompt)
