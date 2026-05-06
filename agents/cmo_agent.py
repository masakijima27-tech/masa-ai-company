from agents.base_agent import BaseAgent
from agents.content_agent import ContentAgent
from agents.campaign_agent import CampaignAgent
from config.settings import FACILITY

SYSTEM_PROMPT = f"""あなたは{FACILITY['name']}（{FACILITY['location']}）のチーフマーケティングオフィサー（CMO）です。

## 役割
- マーケティング戦略の統括・意思決定
- コンテンツチーム・キャンペーンチームへの指示出し
- KPI管理と改善提案
- バンコクのウェルネス市場に精通した戦略家

## 対象施設
- バンコクにあるプレミアムサウナ施設
- ターゲット: 駐在員、タイ人富裕層、観光客、健康志向層
- 対応言語: 日本語・英語・タイ語

## 行動指針
- データドリブンな意思決定
- 各エージェントの専門性を活かした指示
- 実行可能で具体的な戦略を提案
- 日本語でコミュニケーション

ユーザーからの依頼を受けたら、必要に応じてコンテンツチームやキャンペーンチームに具体的な指示を出し、
統合されたマーケティング戦略をまとめてください。"""


class CMOAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CMO",
            role="Chief Marketing Officer",
            system_prompt=SYSTEM_PROMPT,
        )
        self.content_agent = ContentAgent()
        self.campaign_agent = CampaignAgent()

    def orchestrate(self, request: str) -> dict:
        """ユーザーの依頼を受けて各エージェントに指示し結果を統合する"""
        # CMOが戦略を立案
        strategy = self.run(
            f"""以下の依頼に対して、マーケティング戦略を立案してください。
また、コンテンツチームとキャンペーンチームへの具体的な指示内容も含めてください。

依頼: {request}

出力形式:
1. 戦略概要
2. コンテンツチームへの指示（広告文・クリエイティブ要件）
3. キャンペーンチームへの指示（キャンペーン設計・スケジュール）
4. KPI・成功指標"""
        )

        # コンテンツエージェントに広告文生成を依頼
        content_brief = f"CMOからの指示に基づき、バンコクのサウナ施設の広告コンテンツを作成してください。\n\nCMO戦略:\n{strategy}\n\n元の依頼: {request}"
        content = self.content_agent.run(content_brief)

        # キャンペーンエージェントに企画を依頼
        campaign_brief = f"CMOからの指示に基づき、バンコクのサウナ施設のキャンペーンを企画してください。\n\nCMO戦略:\n{strategy}\n\n元の依頼: {request}"
        campaign = self.campaign_agent.run(campaign_brief)

        # CMOが統合レポートを作成
        final_summary = self.run(
            f"""コンテンツチームとキャンペーンチームの成果物を受け取りました。
統合されたマーケティングプランとして最終レポートをまとめてください。

【コンテンツチームの成果】
{content}

【キャンペーンチームの成果】
{campaign}

最終レポートには実装優先順位と次のアクションを含めてください。"""
        )

        return {
            "strategy": strategy,
            "content": content,
            "campaign": campaign,
            "final_report": final_summary,
        }
