FROM python:3.13-slim

WORKDIR /app

# 必要なパッケージをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 環境変数のデフォルト値設定
ENV LARGE_AMOUNT_THRESHOLD=50000
ENV TRANSFER_DAYS_WINDOW=3
ENV TRANSFER_AMOUNT_TOLERANCE=1000

# アプリケーションコードをコピー
COPY . .

# データを永続化するためのボリュームポイント
VOLUME /app/data

# Streamlitのポートを開放
EXPOSE 8501

# 起動コマンド
CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0"]
