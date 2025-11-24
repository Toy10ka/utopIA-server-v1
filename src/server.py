# server.py
from flask import Flask, request, Response, jsonify
import requests, json
# stt用
import io
import os

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

# Flask: アプリケーションを作るクラス。
# request: クライアントから送られてきたリクエスト情報を扱うオブジェクト。
# Response: レスポンスを自分で組み立てたいときに使うクラス。
# jsonify: Python の辞書やリストを JSON 形式に変換して返す便利関数。

# requests: 他のHTTPサーバーにアクセスするためのライブラリ。
# json: Python 標準の JSON エンコード/デコードモジュール。

# soundfile (sf): WAV / Ogg / FLAC などの音声ファイルを読み書きするライブラリ
   # Python 標準の wave より高機能で、Whisper の前処理によく使われる
# faster_whisper: Whisper を高速化した推論ライブラリ（CTranslate2 ベース）
   # GPU/CPU 両方で動作し、量子化 (float16 / int8 など) に対応

# ---------------------------------------------------------------

# STT (faster-whisper) 設定

# 環境変数の読み込み
STT_MODEL_NAME = os.getenv("STT_MODEL_NAME", "large-v3") # 設定されていなければlarge-v3
STT_COMPUTE_TYPE = os.getenv("STT_COMPUTE_TYPE", "float16")  # 設定されていなければfloat16 (int8_float16にするかも)
STT_DEVICE = os.getenv("STT_DEVICE", "cuda")  # 設定されていなければcuda (cpuにもできる)

# 読み込んだモデルの実体を保持 (最初は空)
_whisper_model = None

# モデル取得関数 (シングルトン)
def get_whisper_model():
    """遅延初期化（Lazy Initialization）パターン：必要になるまでオブジェクトを生成（初期化）しない"""
    # global宣言：関数の外で定義された変数 _whisper_model を書き換える
    global _whisper_model
    # モデルがまだ読み込まれていない場合（Noneの場合）のみロードを実行
    if _whisper_model is None:
        # ログ出力
        app.logger.info(
            "[STT] loading faster-whisper model=%s device=%s compute_type=%s",
            STT_MODEL_NAME,
            STT_DEVICE,
            STT_COMPUTE_TYPE,
        )
        # クラス初期化（モデルをメモリに展開）
        _whisper_model = WhisperModel(
            STT_MODEL_NAME,
            device=STT_DEVICE,
            compute_type=STT_COMPUTE_TYPE,
        )
    # モデルを呼び出し元に返却（二回目以降は即座にここにきて既存モデルを返却）
    return _whisper_model

# ------------

# Whisperの要件（float32 / mono / 16kHz の NumPy 配列）にリサンプリングする関数
   # Unity 側を 16kHz モノラルで録音しておけば必要ない（保険）
def decode_wav_to_mono(audio_bytes: bytes): # バイナリデータ（bytes型）を受け取る
    """
    - bytes から WAV を読み込む
    - モノラル float32 に変換
    - サンプリングレートを必要なら 16kHz にリサンプリング
    """
    # soundfileはファイルパスを要求するため，メモリ上のデータ（bytes）をファイルのように偽装
    with io.BytesIO(audio_bytes) as f:
        # soundfile (sf)で音声を読み込む
        # 戻り値: audio（波形データ配列）と sample_rate（1秒間のサンプル数）
        audio, sample_rate = sf.read(f, dtype="float32")

    # Whisperはステレオ（左右2チャンネル）ではなくモノラル（1チャンネル）の音声を要求
    # audio.shape: (samples,) or (samples, channels)
    if audio.ndim == 1: # データが1列しかない＝元からモノラル
        num_channels = 1
        audio_mono = audio
    else: # ステレオやマルチチャンネル
        num_channels = audio.shape[1]
        audio_mono = audio.mean(axis=1) # (左の音 + 右の音) ÷ 2

    # 音声の長さ（秒）を計算 
    duration_sec = float(len(audio_mono) / sample_rate)

    target_sr = 16000
    # 16khzでない場合
    # SciPyなし（numpyだけ）の単純な線形補間のリサンプリング
    if sample_rate != target_sr:
        # 変換後にデータが何個（何サンプル）になるか (ex. 48なら1/3に)
        num_samples = int(len(audio_mono) * target_sr / sample_rate)
        # リサンプリングのための時間軸
        x_old = np.linspace(0.0, 1.0, len(audio_mono), endpoint=False)
        x_new = np.linspace(0.0, 1.0, num_samples, endpoint=False)
        # 線形補間（x_newがx_old, audio_monoのどこにあたるか）
        audio_mono = np.interp(x_new, x_old, audio_mono).astype("float32")
        # 更新
        sample_rate = target_sr

    return audio_mono, sample_rate, num_channels, duration_sec

# ---------------------------------------------------------------

# Flask アプリケーションの生成
app = Flask(__name__)
app.json.ensure_ascii = False  # 日本語をそのまま返す(デフォルトのTrueだとunicodeに変換される)
# 外部APIのエンドポイント
OLLAMA = "http://ollama:11434/api/chat"
VVE    = "http://voicevox-engine:50021"

# 起動時にSTTモデルをプリロード
if os.getenv("STT_PRELOAD", "1") == "1":
    get_whisper_model()

# ---------------------------------------------------------------

# メソッド作成

# ---------- LLM ----------

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

# ---------- TTS ----------

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

# ---------- STT ----------

# APIレスポンスの作成
# 生の音声データ（bytes）を受け取り、結果を辞書（dict）で返す
def run_stt(audio_bytes: bytes) -> dict:
    # メモリ上のモデルを取得
    model = get_whisper_model()
    # 前処理
    audio_mono, sample_rate, num_channels, duration_sec = decode_wav_to_mono(audio_bytes)

    # 文字起こしの実行
    # fwの核心メソッド transcribe （音声 → 文字列の断片を生成するジェネレータ）呼び出し
    """
       segments_iter … ジェネレータ（文字断片を順次生成）
        seg.start = 1.23
        seg.end = 3.87
        seg.text = "こんにちは"
        seg.avg_logprob = -0.10
        seg.no_speech_prob = 0.02 …
       info … メタ情報（言語推定結果など）
    """
    segments_iter, info = model.transcribe(
        audio_mono,
        language=None,  # 言語自動判定（"ja"になるだろう）
        beam_size=5, # 音声 → トークン列の予測幅 (大きいほど精度高い)
        vad_filter=True, # 無音部分の切り取りフィルタ有効
        vad_parameters=dict(
            min_silence_duration_ms=500, # 0.5s以上無音で切る (幻覚を防げる)
            speech_pad_ms=200, # 切った音声前後に0.2sのパディング
        ),
    )
    # 結果の格納
    segments_out = [] # タイムスタンプ付きの詳細データ用
    texts = [] # 文字列だけの結合用
    
    # 文字起こし（ジェネレータを回し，認識された文章の断片（seg）を一つずつ取り出す）
    for seg in segments_iter:
        """
        texts → 人が読みやすい全文
        segments_out → タイムスタンプ付きの専門情報
        """
        # 1. 人が読む用

        # segの中身がNoneなら空文字に置き換えて .strip()
        seg_text = (seg.text or "").strip()
        # 空文字でない場合のみ処理
        if seg_text:
            # クリーンテキストのみを連結して格納
            texts.append(seg_text)

        # 2. デバッグ用・メタ情報用
        segments_out.append(
            {
                "start": float(seg.start),
                "end": float(seg.end),
                "text": seg.text,
                "avg_logprob": float(seg.avg_logprob), # Whisper の出力の平均対数確率 (0に近いと良い)
                "no_speech_prob": float(seg.no_speech_prob), # 音声がないと判断した確率 (VADの参考)
            }
        )

    # 最終レスポンスの構築
    # 半角スペースを間に入れてテキストを全て繋げる
    full_text = " ".join(texts).strip()
    # 言語コード取得（自動判定したもの）
    language = getattr(info, "language", None) or "unknown"
    # 音声の長さ（infoから取れない場合は前処理で計算したものを使う）
    duration = float(getattr(info, "duration", duration_sec))
    
    # 最終的に返却する大きな辞書を作成
    result = {
        "text": full_text,
        "language": language,
        "duration_sec": duration,
        "segments": segments_out,
        "meta": {
            "model": getattr(info, "model_name", STT_MODEL_NAME),
            "compute_type": STT_COMPUTE_TYPE,
            "sample_rate": sample_rate,
            "num_channels": num_channels,
            "vad_enabled": True,
        },
    }
    return result

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

# デバッグ用：テキスト({"text":"hoge"})だけ欲しい際のAPI
@app.post("/api/ask_text")
def api_ask_text():
    body = request.get_json(force=True)
    return jsonify({"text": ask_llm_text(body["prompt"])})

# -----------------

# stt用
@app.post("/api/stt")
def api_stt():
    """
    音声(WAV) → テキスト
    リクエスト: Content-Type: audio/wav, body = WAVバイト列
    レスポンス: 上記 run_stt() の dict を JSON で返す
    """
    # リクエストのボディを確認
    if not request.data:
        return jsonify({"error": "no_audio", "message": "request body is empty"}), 400

    try:
        # リクエストから取り出した生のバイナリデータ request.dataを渡す
        result = run_stt(request.data)
        return jsonify(result)
    except Exception as e:
        app.logger.exception("STT failed")
        return jsonify({"error": "stt_failed", "message": str(e)}), 500

