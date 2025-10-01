# utopIA-v1

Unity から HTTP で叩ける **テキスト→LLM→音声合成** ゲートウェイ。  
Docker Compose で **Ollama（LLM）** と **VOICEVOX ENGINE（TTS）** を起動し、  
Flask（utopia-server）が両者を中継します。

## 機能
- `/api/ask_text` : プロンプト→LLM テキスト（日本語指定）
- `/api/ask_tts`  : プロンプト→LLM テキスト→VOICEVOX で WAV 返却
- 端末からの動作確認用シェル（`u-ollama-chat.sh`, `u-vve.sh`, `u-ask-tts.sh`）
- Dev Containers 対応（VS Code でそのまま開発）

## 構成
```
Unity ─HTTP→ utopia-server(Flask) ─HTTP→ ollama(LLM)
                               └───HTTP→ voicevox-engine(TTS)
```

## 前提
- Docker Desktop（NVIDIA GPU があれば CUDA で高速化）
- VS Code + Dev Containers（任意）

## クイックスタート
```bash
# 1) 起動
docker compose up -d

# 2) 開発コンテナへ（VS Code: 「コンテナで再度開く」）
# もしくはホストから: docker compose exec utopia-server bash

# 3) LLM モデルの用意（初回のみ）
docker compose exec ollama sh -lc "ollama pull llama3:8b"

# 4) 単体テスト（VOICEVOX: WAV 生成）
docker compose exec utopia-server bash -lc '
printf "こんにちは、テストです。" > /tmp/text.txt &&
curl -sG "http://voicevox-engine:50021/audio_query"   --data-urlencode "text@/tmp/text.txt" --data-urlencode "speaker=1" > /tmp/q.json &&
curl -s -X POST "http://voicevox-engine:50021/synthesis?speaker=1"   -H "Content-Type: application/json" --data-binary @/tmp/q.json -o /app/audio.wav
'
# ホスト側: ./src/audio.wav ができていればOK

# 5) サーバをアプリとして起動（CMD が gunicorn の場合は不要）
docker compose exec utopia-server bash -lc "python server.py"
```

## エンドポイント（utopia-server / Flask）
- **POST `/api/ask_text`**
  - req: `{"prompt":"ラーメンの魅力を一文で。"}`
  - res: `{"text":"..."}`

- **POST `/api/ask_tts`**
  - req: `{"prompt":"自己紹介を一文で。","speaker":1}`
  - res: `audio/wav`（バイナリ）

> 内部では `/api/chat`（Ollama）と `/audio_query` `/synthesis`（VOICEVOX）を使用。  
> モデル常駐には `keep_alive: "10m"` を付与。

## ディレクトリ
```
.
├─ .devcontainer/          # VS Code Dev Containers 設定
├─ src/
│  ├─ server.py            # Flask アプリ
│  ├─ u-ollama-chat.sh     # LLM 単体テスト
│  ├─ u-vve.sh             # VOICEVOX 単体テスト
│  └─ audio.wav            # 生成物（.gitignore 対象）
├─ docker-compose.yml
├─ Dockerfile
├─ requirements.txt
├─ .gitignore
└─ .dockerignore
```

## よく使うコマンド
```bash
# ログ
docker compose logs -f utopia-server
docker compose logs -f ollama
docker compose logs -f voicevox-engine

# モデル一覧 / 追加
docker compose exec ollama sh -lc "ollama list"
docker compose exec ollama sh -lc "ollama pull llama3:8b"

# ヘルスチェック（例）
curl -s http://ollama:11434/api/tags | jq .
curl -s http://voicevox-engine:50021/version
```

## Unity からの呼び出し例（擬似コード）
```csharp
var json = JsonUtility.ToJson(new { prompt = "自己紹介を一文で。" });
using var client = new HttpClient();
var res = await client.PostAsync("http://<host>:5000/api/ask_tts",
    new StringContent(json, Encoding.UTF8, "application/json"));
File.WriteAllBytes("answer.wav", await res.Content.ReadAsByteArrayAsync());
```

## トラブルシュート
- **WAV が 1KB / 再生不可**: `audio_query` を `--data-urlencode`、`synthesis` は `--data-binary @` で送る。  
- **日本語が通らない**: JSONは UTF-8。Windows ターミナルは UTF-8 / スクリプトは LF を推奨。  
- **初回だけ遅い**: モデルのプレウォーム or `keep_alive: "10m"` を付与。  
- **コンテナ間疎通**: `http://サービス名:ポート` を使う（`localhost` は×）。

## ライセンス
- このリポジトリ: MIT（例）  
- VOICEVOX ENGINE / モデル: それぞれのライセンスに従うこと
