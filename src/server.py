# Flaskサーバ作成
from flask import Flask

# 実体生成
app = Flask(__name__)

# ルーティング（ローカルURLと処理の対応決め）
@app.route("/")
def index():
    return "Hello from utopIA server!"