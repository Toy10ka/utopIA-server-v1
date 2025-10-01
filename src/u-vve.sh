# utopia-serverからvoicevox-engineコンテナにHTTPリクエスト
# chmod +x ./u-vve.sh 

# ----------------------------


# 1) テキストをUTF-8でファイル化（BOMなし）
echo -n "こんにちは、音声合成の世界へようこそ" > /tmp/text.txt

# 2) /audio_query でクエリ生成（URLエンコードで安全）
curl -s \
  -X POST \
  "http://voicevox-engine:50021/audio_query?speaker=1" \
  --get --data-urlencode text@/tmp/text.txt \
  > /tmp/query.json

# 3) /synthesis でWAVを取得
curl -s \
  -H "Content-Type: application/json" \
  -X POST \
  -d @/tmp/query.json \
  "http://voicevox-engine:50021/synthesis?speaker=1" \
  > /app/audio.wav # ホストの./srcをappにvolumeしていることを忘れない






