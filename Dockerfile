FROM python:3.11-slim

WORKDIR /app

# 必要なパッケージをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# データを永続化するためのボリュームポイント
VOLUME /app/data

# Streamlitのポートを開放
EXPOSE 8501

# 起動コマンド
CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0"]
