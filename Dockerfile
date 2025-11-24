# 構成：GPU ランタイム付きベースイメージを使いつつ、自分の依存だけを追加し、最後に対話シェルを起動
# volumes指定はymlでする予定

# PyTorch の公式ランタイム付きイメージを土台にする
# イメージレイヤ内部にはPython（と pip）がすでに入っている
FROM pytorch/pytorch:2.7.0-cuda11.8-cudnn9-runtime

# Python の出力をバッファリングせず即時に画面へ流す (no buffering)
ENV PYTHONUNBUFFERED=1

# stt用にffmpeg 等を追加
RUN apt-get update \
 && apt-get install -y ffmpeg libsndfile1 \
 && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリを/appに設定
WORKDIR /app

# reqを先にコピー（ボリュームはymlで行う）
COPY requirements.txt .

# 依存関係インストール
# faster-whisperにlibcublas.so.12が必要だが，ベースイメージにはlibcublas.so.11しかない
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir nvidia-cublas-cu12 nvidia-cudnn-cu11

# libcublas.so.12があるディレクトリをコンテナの環境変数に追加
ENV LD_LIBRARY_PATH=/opt/conda/lib/python3.11/site-packages/nvidia/cudnn/lib:/opt/conda/lib/python3.11/site-packages/nvidia/cublas/lib:$LD_LIBRARY_PATH
# ------------------ここまでひな形------------------

# ポートの公開 (Flask のデフォルトポートが 5000)
EXPOSE 5000  

# gunicornでサーバ立てる
# Flask-Sock 等でWebSocketを使う
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "300", "-k", "geventwebsocket.gunicorn.workers.GeventWebSocketWorker", "server:app"]