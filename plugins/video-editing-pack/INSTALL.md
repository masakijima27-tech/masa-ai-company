# 初回セットアップ

所要15〜30分（Whisperモデルのダウンロード時間が大半です）。
迷ったら、先に Claude Code にこのフォルダを読ませて
「セットアップして」と言えば、doctor の結果を見ながら1つずつ案内してくれます。

## 1. パックを Claude Code に入れる

どちらか片方でOKです。

### 方法A: ターミナルから（確実・30秒）

1. ZIPを任意の場所に解凍する（例: `~/Downloads/video-editing-pack/`）
2. ターミナルで Claude Code を起動する
   ```bash
   claude
   ```
3. プロンプトに次の2行を順に入力する
   ```
   /plugin marketplace add ~/Downloads/video-editing-pack
   /plugin install video-editing-pack@video-editing-pack
   ```
4. Claude Code を再起動すると video-editing スキルが使える

### 方法B: デスクトップアプリの画面から

アプリのプラグイン管理画面（バージョンによりプラグイン設定の場所が違います。
見つからなければサイドバーの「もっと見る」やプロンプト横の「＋」からプラグインを探してください）で
ローカルアップロードを選び、解凍したフォルダを指定します。
見つからない場合は方法Aへ。

## 2. 必要ソフトを入れる

### Mac（M1 / M2 / M3 / M4）

```bash
brew install ffmpeg
pip3 install pillow mlx-whisper
```

### Mac（Intel・2020年以前の機種）

```bash
brew install ffmpeg whisper-cpp
pip3 install pillow
python3 skills/video-editing/scripts/doctor.py --download-model small
```

古いMacは処理に時間がかかるので、軽量モデル（small）を推奨します。
精度を上げたい場合は `--download-model` を引数なしで実行すると高精度版が入ります。

### Windows

```powershell
winget install ffmpeg
winget install Python.Python.3.12
pip install pillow faster-whisper
```

PowerShell は「管理者として実行」で開いてください。
winget が使えない場合は ffmpeg.org と python.org から手動インストールでもOKです。

## 3. 動作確認

```bash
python3 skills/video-editing/scripts/doctor.py
```

全部OKになれば完了です。NGがあれば、表示されるヒント通りに入れてください。

## 4. 最初の1本

```
この動画テロップ入れて /パス/動画.MOV
```

と Claude Code に話しかければ、縦リールか横講座かを聞かれた後、全自動で完成します。

## よくあるつまずき

- **pip3 が見つからない** → Python が入っていません。手順2のPythonインストールから
- **brew が見つからない（Mac）** → brew.sh の1行コマンドで Homebrew を先に入れる
- **文字起こしが遅い** → モデルを small にする（doctor.py --download-model small）
- **処理中にファンが全開になる** → 正常です。動画の再エンコードはCPUを使い切ります
