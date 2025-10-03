# utopia-serverからvoicevox-engineコンテナにHTTPリクエスト
# chmod +x ./u-vve.sh 

# ----------------------------


# 1) テキストをUTF-8でファイル化 (直で日本語をURLに乗せると文字化けの恐れがあるため)
echo -n "こんにちは、音声合成の世界へようこそ" > /tmp/text.txt

# 2) /audio_query でクエリ生成（URLエンコードで安全）
# text: クエリパラメータで渡す
# speaker: クエリパラメータで渡す
curl -s \
  -X POST \
  "http://voicevox-engine:50021/audio_query?speaker=1" \
  # URL エンコードし、クエリパラメータとして付与 
  --get --data-urlencode text@/tmp/text.txt \
  > /tmp/query.json

# 3) /synthesis でWAVを取得
# speaker: クエリパラメータで渡す
# audio_query の結果(JSON): リクエストボディで渡す
curl -s \
  -H "Content-Type: application/json" \
  -X POST \
  -d @/tmp/query.json \
  "http://voicevox-engine:50021/synthesis?speaker=1" \
  > /app/audio.wav # ホストの./srcをappにvolumeしていることを忘れない






