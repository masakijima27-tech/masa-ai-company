#!/bin/bash
# face-stamp の初回セットアップ（1回だけ実行すればいい）
#   bash scripts/setup_env.sh
set -e
cd "$(dirname "$0")/.."

PY=""
for c in python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "Python が見つかりません"; exit 1; }
echo "使う Python: $($PY --version) ($(command -v $PY))"

[ -d .venv ] || "$PY" -m venv .venv
./.venv/bin/pip install -q --disable-pip-version-check --upgrade pip

# バージョンを固定して入れる（固定しないと pip が古いソース配布を延々と探しに行って固まる）
./.venv/bin/pip install -q --disable-pip-version-check --progress-bar off \
  "numpy<3" "opencv-python-headless==4.12.0.88" || {
  echo "opencv の導入に失敗しました。macOS が古い場合は下のバージョンを試してください:"
  echo "  macOS 12 まで → opencv-python-headless==4.10.0.84"
  echo "  macOS 11 まで → opencv-python-headless==4.9.0.80"
  exit 1
}

# 顔検出モデル（無ければ facestamp.py 実行時にも自動取得される）
MODEL=assets/face_detection_yunet_2023mar.onnx
if [ ! -s "$MODEL" ]; then
  echo "顔検出モデルを取得中…"
  curl -sSL -o "$MODEL" \
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
fi

command -v ffmpeg >/dev/null 2>&1 || echo "※ ffmpeg が入っていません: brew install ffmpeg"

./.venv/bin/python -c "import cv2, numpy; print('opencv', cv2.__version__, '/ numpy', numpy.__version__)"
echo "セットアップ完了。次は SKILL.md の手順どおり --preview 10 で試してください。"
