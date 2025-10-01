# 構成：GPU ランタイム付きベースイメージを使いつつ、自分の依存だけを追加し、最後に対話シェルを起動
# volumes指定はymlでする予定

# PyTorch の公式ランタイム付きイメージを土台にする
# イメージレイヤ内部にはPython（と pip）がすでに入っている
FROM pytorch/pytorch:2.7.0-cuda11.8-cudnn9-runtime

# Python の出力をバッファリングせず即時に画面へ流す (no buffering)
ENV PYTHONUNBUFFERED=1

# 作業ディレクトリを/appに設定
WORKDIR /app

# reqを先にコピー（ボリュームはymlでやる）
COPY requirements.txt .

# 依存関係インストール
RUN pip install --no-cache-dir -r requirements.txt

# ------------------ここまでひな形------------------

# ポートの公開 (Flask のデフォルトポートが 5000)
EXPOSE 5000  

# gunicornでサーバ立てる (ここでCMD使うからymlで上書きしない)
# CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "server:app"]

# ★Flask-Sock 等でWebSocketを使うならこちらに置換
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "-k", "geventwebsocket.gunicorn.workers.GeventWebSocketWorker", "server:app"]