# video-editing-pack

しゃべり動画を渡すだけで、カット編集とテロップ入れが全自動で終わるスキルパックです。
Claude Code に動画ファイルのパスを渡して「テロップ入れて」と言うだけで、
次の工程が一気通貫で走ります。

1. 無音の自動カット（間延びした部分を詰める）
2. word単位の文字起こし（Whisper）
3. フィラー除去（えー、えっと、などを自動カット）
4. 整音（音量を配信標準の -14LUFS に統一）
5. テロップ焼き込み（発話タイミングに同期。改行はGoogle製の日本語改行エンジンBudouXを同梱していて、単語や文節の途中で切れない）
6. 品質チェック（解像度・尺・音量・テロップ整合を自動検査）
7. 納品ファイル出力

## 仕上がりの形（2ルート）

| ルート | 用途 | 仕様 |
|---|---|---|
| 縦リール | Instagram リール / TikTok / YouTubeショート | 1080x1920・白テロップ・中央下 |
| 横講座 | YouTube 講義・解説 | 1920x1080・黄テロップ・画面下部 |

## 出力形式

- 完成MP4（テロップ焼き込み済み）
- SRT字幕ファイル（YouTubeの字幕アップロード用）
- FCPXML（カット済みタイムライン。Final Cut Pro で続きを編集したい人向け）

## 使い方

Claude Code を起動して、こう話しかけるだけです。

```
この動画テロップ入れて /Users/me/Downloads/IMG_1234.MOV
```

聞かれるのは2つだけ（縦リールか横講座か、出力は何か）。あとは全自動です。
初回だけ環境セットアップが必要です（INSTALL.md 参照、15〜30分）。

## こだわりの指定もできる

話しかけるときに伝えれば反映されます。

- 「冒頭3秒はカットして」
- 「無音は0.7秒から詰めて」（テンポ重視）
- 「フィラー除去は強めで」「フィラーは残して」
- 「1:04から1:08は丸ごと消して」
- 「テロップは黄色で、もう少し下に」

## 誤変換の辞書登録

Whisperが毎回間違える固有名詞は `assets/vocabulary.json` に登録すると
次回から自動で直ります。書き方は `assets/vocabulary.example.json` を参照。

## 品質チェック（自動）

出力前に次の4点を機械チェックし、NGなら納品をブロックします。

- 解像度がルート通りか
- 尺がカット計画と一致しているか
- 音量が -14LUFS に収まっているか
- テロップの重なり・はみ出し・文字数超過がないか

さらに、テロップ表示中のフレーム画像を数枚書き出すので、目視確認もすぐできます。

## 動作要件

| 必須 | 入れ方 |
|---|---|
| Python 3.9+ | python.org |
| ffmpeg | Mac: `brew install ffmpeg` / Win: `winget install ffmpeg` |
| Pillow | `pip3 install pillow` |
| Whisper系いずれか1つ | Mac(M1以降): `pip3 install mlx-whisper` / Win: `pip3 install faster-whisper` / 古いMac等: `brew install whisper-cpp` |

環境チェックは `python3 skills/video-editing/scripts/doctor.py` で。足りないものと入れ方だけ表示されます。

## フォルダ構成

```
video-editing-pack/
├── README.md                  ← この文書
├── INSTALL.md                 ← 初回セットアップ手順
├── CLAUDE.md                  ← Claude Code への指示
├── skills/video-editing/
│   ├── SKILL.md               ← スキル本体（発火条件と手順）
│   └── scripts/
│       ├── pipeline.py        ← 全工程オーケストレーター
│       ├── doctor.py          ← 環境チェック＋モデル取得
│       ├── transcribe.py      ← 文字起こし（3バックエンド自動判別）
│       ├── jetcut.py          ← 無音・フィラーカット
│       ├── audio_master.py    ← 整音
│       ├── captions.py        ← テロップ行生成・語彙補正
│       ├── render.py          ← テロップ焼き込み
│       ├── qc.py              ← 品質チェック
│       └── export.py          ← MP4 / SRT / FCPXML 出力
└── assets/
    ├── fonts/                 ← テロップ用フォント置き場（未同梱の軽量版では
    │                             Mac/Windows標準の太ゴシックに自動代替）
    └── vocabulary.example.json
```

## ライセンス

LICENSE.txt を参照してください。
同梱フォントは SIL Open Font License 1.1 です。
