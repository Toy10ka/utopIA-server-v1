# server.py
from flask import Flask, request, Response, jsonify
import requests, json

# Flask … アプリケーションを作るクラス。
# request … クライアントから送られてきたリクエスト情報を扱うオブジェクト。
# Response … レスポンスを自分で組み立てたいときに使うクラス。
# jsonify … Python の辞書やリストを JSON 形式に変換して返す便利関数。

# requests: 他のHTTPサーバーにアクセスするためのライブラリ。
# json: Python 標準の JSON エンコード/デコードモジュール。

# ---------------------------------------------------------------

# アプリ本体と外部APIエンドポイント設定

# Flask アプリケーションの生成
app = Flask(__name__)
app.json.ensure_ascii = False  # ← 追加（Flaskに日本語をそのまま出させる）（jsonfyはデフォでTrue）
# 外部APIのエンドポイント
OLLAMA = "http://ollama:11434/api/chat"
VVE    = "http://voicevox-engine:50021"

# ---------------------------------------------------------------

# メソッド作成

# 関数(u-ollama-chat.sh)：ollamaにreqests.postを飛ばし, レスポンスrからtextを取得
# (入力)プロンプト，モデル, (出力)text
def ask_llm_text(prompt, model="llama3:8b"):
    payload = {
        "model": model,
        "messages": [
		        # モデルへの指示
            {"role":"system","content":"出力は必ず日本語。ローマ字禁止。"},
            # プロンプト
            {"role":"user","content": prompt}
        ],
        "stream": False, # 後々Trueにしたい
        "keep_alive": "10m"
    }
    # ollamaへのリクエスト（r：レスポンス）
    r = requests.post(OLLAMA, 
		    # ボディ(json形式)でリクエストを送信
		    json=payload, # requests.postはjsonが引数にあり，自動変換される
		    timeout=300) 
    r.raise_for_status() # HTTPエラーがあれば例外を投げる(404など)
    # レスポンスをjsonに変換
    data = r.json()
    # messageのcontentを取り出す
    text = (data.get("message") or {}).get("content", "")
    # 改行をTTS前に潰す（任意）
    return text.replace("\r","").replace("\n","")
# -----------------

# 関数(u-vve.sh)：vveにtextをreqests.postし，レスポンスqからwavを得る
# (入力)text, 話者, (出力)wav
def tts_voicevox(text, speaker=1):
    # 1) audio_query
    q = requests.post(
		    # エンドポイント/audio_queryでjson生成
        f"{VVE}/audio_query",
        # クエリパラメータで文字列と話者IDを送信 
        params={"text": text, "speaker": speaker},
        timeout=60
    )
    # エラーで例外を投げる
    q.raise_for_status()
    # レスポンスをjson形式 に
    query = q.json()
    # ここで query({["speedScale"],["pitchScale"] …})，音声の速さや高さを調整可

    # 2) synthesis
    wav = requests.post(
        f"{VVE}/synthesis",
        params={"speaker": speaker}, # speakerはクエリパラメータで投げる
        json=query, # queryはボディで投げる
        timeout=300
    )
    wav.raise_for_status()
    return wav.content
    
# ---------------------------------------------------------------

# ルーティング（API定義）

# postリクエスト対応
# 入力：json (ex. {"prompt": "おはよう！","speaker": 3})
@app.post("/api/ask_tts") # エンドポイント
def api_ask_tts(): # 処理
		# リクエストのjsonをbodyに格納
    body = request.get_json(force=True) # 自動で辞書になる
    # プロンプトを取り出す
    prompt = body["prompt"]
    # 話者を取り出す（なければ1を返す）
    speaker = int(body.get("speaker", 1)) # dict.get() : なければデフォ値を返す
    try:
		    # ollama問い合わせ
        text = ask_llm_text(prompt) 
        # vve問い合わせ
        audio = tts_voicevox(text, speaker)
        # Responseオブジェクト（応答のカスタム）
	        # WAVはバイナリなので，デフォだとmimetype=text/htmlになる
        return Response(audio, mimetype="audio/wav") # audioをレスポンス本文に
    except requests.HTTPError as e:
		    # エラー時レスポンス(json)を返す
        return jsonify({"error":"upstream error", "detail": str(e)}), 502
        
# -----------------

# デバッグ用：テキスト({"text":"hoge"})だけ欲しい時のAPI
@app.post("/api/ask_text")
def api_ask_text():
    body = request.get_json(force=True)
    return jsonify({"text": ask_llm_text(body["prompt"])})

