FROM python:3.9-slim

WORKDIR /app

# ファイルをすべてコピー
COPY . .

# 必要なライブラリをインストール
RUN pip install --no-cache-dir -r requirements.txt

# Cloud Runが指定するポート（標準8080）でStreamlitを起動
CMD streamlit run app.py --server.port=${PORT:-8080} --server.address=0.0.0.0

