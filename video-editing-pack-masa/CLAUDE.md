# video-editing-pack

動画のカット編集＋テロップ焼き込みを全自動で行うスキルパックです。

## 収録スキル

| スキル | 用途 |
|---|---|
| `skills/video-editing` | カット＋テロップ焼き込み（本体） |

## ルール

- 動画ファイル（.mov / .mp4 / .m4a）＋編集依頼が来たら、必ず `skills/video-editing/SKILL.md` の手順に従う
- 実作業は `skills/video-editing/scripts/pipeline.py` に任せる。ffmpegコマンドを自分で組み立てて代替しない
- 品質改札（qc）が通るまで完成扱いにしない
- 環境の相談（動かない・初回設定）は `scripts/doctor.py` を実行して、NG項目だけを1つずつ案内する
