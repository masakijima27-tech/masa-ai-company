# video-editing-pack

動画のカット編集＋テロップ焼き込みを全自動で行うスキルパックです。

## 収録スキル

| スキル | 用途 |
|---|---|
| `skills/video-editing` | カット＋テロップ焼き込み（本体） |
| `skills/face-stamp` | 顔出しNGの人の顔にスタンプを自動追従させる |

## ルール

- 動画ファイル（.mov / .mp4 / .m4a）＋編集依頼が来たら、必ず `skills/video-editing/SKILL.md` の手順に従う
- 顔を隠す動画は、パイプラインに `--stamp <PNG>` を渡す（カット→テロップ→スタンプまで一気通貫）。
  スタンプだけ単体で乗せたいときは `skills/face-stamp/SKILL.md`
- masaさんの動画は `--stamp skills/face-stamp/assets/masa_stamp.png`。それ以外はスタンプなし
- 実作業は `skills/video-editing/scripts/pipeline.py` に任せる。ffmpegコマンドを自分で組み立てて代替しない
- 品質改札（qc）が通るまで完成扱いにしない
- 環境の相談（動かない・初回設定）は `scripts/doctor.py` を実行して、NG項目だけを1つずつ案内する

## 配布物の作り方

このフォルダが**原本**。直すのは常にここ。配布用は毎回ここから作り直す（2箇所を手で直さない）。

```bash
bash make_dist.sh
```

- `dist/video-editing-pack/` … コンサル生用（カット＋テロップのみ。顔スタンプは入らない）
- `dist/video-editing-pack-masa/` … masaさん用（顔スタンプ込み・masaさんのキャラ同梱）
