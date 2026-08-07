# 初回セットアップ

所要15〜30分（ほとんどは待ち時間です）。

**迷ったら、Claude Code にこのフォルダを渡して「セットアップして」と言ってください。**
不足しているものを1つずつ案内してくれます。以下はその手順書です。

---

## STEP 0. どっちで動かすか（ここが分かれ道）

Claude Code には **デスクトップアプリ版** と **ターミナル版** があります。

**はじめての方は、必ずデスクトップアプリ版を使ってください。**

ターミナル版は、作業の途中で「このコマンドを実行していい？」という確認が**黒い画面に英文で**出ます。
慣れていないと、1回ずつ内容を確かめることになって消耗します（実際、そうなった方がいます）。
デスクトップアプリ版なら同じ確認がボタンで出るので、判断がずっと楽です。

さらにSTEP 3で、その確認自体をほとんど出ないようにします。

---

## STEP 1. パックを Claude Code に入れる

1. ZIPを解凍する（例: `~/Downloads/video-editing-pack/`）
2. Claude Code を開く
3. 入力欄に **1行目だけ** を貼ってEnter（2行まとめて貼らないこと）

   ```
   /plugin marketplace add ~/Downloads/video-editing-pack
   ```

   確認が出たらEnterで進めます

4. 終わったら **2行目** を貼ってEnter

   ```
   /plugin install video-editing-pack@video-editing-pack
   ```

5. Claude Code を再起動する

**うまくいかないとき**

- 2行まとめて貼ると `Path does not exist: ...` というエラーになります。Escで閉じて、1行ずつやり直してください
- 解凍したフォルダ名が `video-editing-pack (2)` のようになっていたら、その名前に合わせてパスを変えてください

---

## STEP 2. 必要なソフトを入れる

### まず、自分のMacがどっちか確かめる

画面左上の **アップルマーク → このMacについて** を開きます。
**チップ** または **プロセッサ** の欄を見てください。

- `Apple M1` `Apple M2` `Apple M3` `Apple M4` などと書いてある → **Apple siliconのMac**
- `Intel` と書いてある → **IntelのMac**

Windowsの方はいちばん下へ。

### Apple siliconのMac

先に Homebrew が入っているか確認します。ターミナル（またはClaude Code）で:

```bash
brew --version
```

**バージョンが表示された** → そのまま次へ。
**`command not found` と出た** → Homebrew が入っていないので、先にこれを実行します:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Macのパスワードを聞かれます。画面には何も表示されませんが入力できているので、そのままEnterで進めてください。
終わったら、画面の最後に出てくる `eval ...` で始まる行を、そのまま実行します（PATHを通す作業です）。

Homebrewが入ったら:

```bash
brew install ffmpeg
pip3 install pillow mlx-whisper
```

### IntelのMac（2020年以前）

```bash
brew install ffmpeg whisper-cpp
pip3 install pillow
python3 skills/video-editing/scripts/doctor.py --download-model small
```

古いMacは処理に時間がかかるので、軽量モデル（small）を使います。

### Windows

PowerShell を「管理者として実行」で開いてから:

```powershell
winget install ffmpeg
winget install Python.Python.3.12
pip install pillow faster-whisper
```

winget が使えない場合は ffmpeg.org と python.org から手動インストールでもOKです。

---

## STEP 3. 毎回「Yes」を押さなくて済むようにする

**ここを飛ばすと、動画1本ごとに何十回も確認を押すことになります。必ずやってください。**

Claude Code の入力欄に、次の1行を貼ってEnter:

```
video-editing-pack/assets/recommended-permissions.json の中身を、~/.claude/settings.json の permissions.allow に追加して
```

Claude Code が、このパックが使うコマンド（`python3` など9個だけ）を許可リストに足してくれます。
1回だけ確認が出るので、そこはOKしてください。終わったら Claude Code を再起動します。

これで、以降の確認はほとんど出なくなります。

**もし確認が出てしまったら**：選択肢の中に
**「今後このコマンドについては聞かない」**（英語なら `Yes, and don't ask again`）
という項目があります。毎回いちばん上のYesを押すのではなく、こちらを選んでください。次から出なくなります。

---

## STEP 4. 動作確認

```bash
python3 skills/video-editing/scripts/doctor.py
```

全部OKになれば完了です。NGがあれば、表示されるヒント通りに入れてください。

---

## STEP 5. 最初の1本

Claude Code に、こう話しかけます。

```
この動画テロップ入れて /パス/動画.MOV
```

動画ファイルは、入力欄にドラッグ&ドロップするとパスが入ります。
縦リールか横講座かを聞かれた後、あとは全自動で完成します。


---

## よくあるつまずき

| 症状 | 原因と対処 |
|---|---|
| 確認のYesが何度も出る | STEP 3をやっていません。戻ってください |
| `pip3 が見つからない` | Python が入っていません。STEP 2から |
| `brew が見つからない`（Mac） | Homebrew が未導入です。STEP 2の確認手順から |
| `Path does not exist` | STEP 1で2行まとめて貼っています。1行ずつやり直し |
| 文字起こしが遅い | モデルを small にする（`doctor.py --download-model small`） |
| 処理中にファンが全開になる | 正常です。動画の再エンコードはCPUを使い切ります |
