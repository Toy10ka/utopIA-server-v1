# ホストからutopia-serverにHTTPリクエスト
# chmod +x

# --------------------------------------------------------

# # a) テキストだけ（/api/ask_text）

# # 1) リクエスト JSON をファイルで用意（UTF-8 / BOM なし）
# cat > req.json <<'JSON'
# {"prompt":"ラーメンの魅力を一文で。"}
# JSON

# # 2) --data-binary でそのまま送る（余計な変換を回避）
# curl -sS -i http://localhost:5000/api/ask_text \
#   -H "Content-Type: application/json; charset=utf-8" \
#   --data-binary @req.json # | jq -r '.text'

# --------------------------------------------------------

# b) 音声（/api/ask_tts）

cat > req.json <<'JSON'
{"prompt":"自己紹介を一文で。","speaker":1}
JSON

curl -sS http://localhost:5000/api/ask_tts \
  -H "Content-Type: application/json; charset=utf-8" \
  --data-binary @req.json \
  -o ./answer.wav