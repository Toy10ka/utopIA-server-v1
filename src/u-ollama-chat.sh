# utopia-serverからollamaコンテナにHTTPリクエスト

# chmod +x ollama-chat.sh：実行権限を付与（最初の一度だけ）

# ------------------------------------------

# ここに直接プロンプトを書く
PROMPT="必ず英語でなく日本語で答えてください．あなたが出力できる文字数の限界は？"

cat > req.json <<JSON
{
  "model": "llama3:8b",
  "messages": [
    {"role":"user","content":"$PROMPT"}
  ],
  "stream": true,
  "keep_alive": "30m" 
}
JSON

curl -sN http://ollama:11434/api/chat \
  -H "Content-Type: application/json" \
  --data-binary @req.json \
| jq -r 'select(.message.content) | .message.content' \
| awk 'BEGIN{ORS="";} {printf "%s", $0; fflush()} END{print ""}'



