FROM python:3.13-slim

# 作業ディレクトリ設定
WORKDIR /app

# システムパッケージの更新と必要なツールのインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 非rootユーザー作成（セキュリティ向上）
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# 必要なパッケージをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 環境変数のデフォルト値設定
ENV LARGE_AMOUNT_THRESHOLD=50000
ENV TRANSFER_DAYS_WINDOW=3
ENV TRANSFER_AMOUNT_TOLERANCE=1000
ENV OLLAMA_BASE_URL=http://ollama:11434

# Streamlit設定
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# アプリケーションコードをコピー
COPY --chown=appuser:appuser . .

# dataディレクトリを作成
RUN mkdir -p data && chown -R appuser:appuser data

# データを永続化するためのボリュームポイント
VOLUME /app/data

# 非rootユーザーに切り替え
USER appuser

# Streamlitのポートを開放
EXPOSE 8501

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# 起動コマンド
CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0"]
