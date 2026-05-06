#!/usr/bin/env python3
"""MASA AI Company - Bangkok Sauna Marketing Agent System"""

import sys
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from agents.cmo_agent import CMOAgent

console = Console()


def print_header():
    console.print(Panel.fit(
        "[bold cyan]MASA AI Company[/bold cyan]\n"
        "[yellow]Bangkok Sauna Marketing Agent System[/yellow]\n"
        "[dim]CMO → Content Agent + Campaign Agent[/dim]",
        border_style="cyan"
    ))


def print_result(result: dict):
    sections = [
        ("戦略概要", result["strategy"]),
        ("広告コンテンツ", result["content"]),
        ("キャンペーン企画", result["campaign"]),
        ("最終レポート", result["final_report"]),
    ]
    for title, content in sections:
        console.print(f"\n[bold green]── {title} ──[/bold green]")
        console.print(Markdown(content))


def run_interactive():
    print_header()
    cmo = CMOAgent()

    console.print("\n[dim]マーケティングの依頼を入力してください。('q' で終了)[/dim]\n")

    while True:
        request = Prompt.ask("[bold cyan]あなた[/bold cyan]")
        if request.lower() in ("q", "quit", "exit"):
            console.print("[dim]終了します。[/dim]")
            break
        if not request.strip():
            continue

        console.print("\n[yellow]エージェントチームが処理中...[/yellow]")
        try:
            result = cmo.orchestrate(request)
            print_result(result)
        except Exception as e:
            console.print(f"[red]エラー: {e}[/red]")


def run_demo():
    """APIキーなしで動作確認するデモモード"""
    print_header()
    console.print("\n[yellow]デモモード（APIキー不要）[/yellow]")
    console.print("\n[bold]エージェント構成:[/bold]")
    console.print("""
┌─────────────────────────────────┐
│     CMO Agent（統括）            │
│  戦略立案・KPI管理・指示出し     │
└────────────┬────────────────────┘
             │
     ┌───────┴────────┐
     ▼                ▼
┌──────────┐  ┌─────────────────┐
│ Content  │  │ Campaign Agent  │
│  Agent   │  │  キャンペーン   │
│ 広告文   │  │  企画・設計     │
│ 生成     │  │                 │
└──────────┘  └─────────────────┘
""")
    console.print("[bold]使用方法:[/bold]")
    console.print("1. .env ファイルに ANTHROPIC_API_KEY を設定")
    console.print("2. pip install -r requirements.txt")
    console.print("3. python main.py")
    console.print("\n[bold]エージェント別コマンド例:[/bold]")
    console.print("  python main.py --content   # 広告文のみ生成")
    console.print("  python main.py --campaign  # キャンペーンのみ設計")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        run_demo()
    elif "--content" in sys.argv:
        from agents.content_agent import ContentAgent
        agent = ContentAgent()
        result = agent.generate_ad_copy("Instagram", "駐在員", "ja")
        console.print(Markdown(result))
    elif "--campaign" in sys.argv:
        from agents.campaign_agent import CampaignAgent
        agent = CampaignAgent()
        result = agent.design_campaign("新規顧客獲得", 50000, 30)
        console.print(Markdown(result))
    else:
        run_interactive()
