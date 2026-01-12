# Dockerでの実行方法

Docker Composeを使用して、相続税通帳分析システムとOllama（LLM）を一括で起動できます。

## 前提条件
- Docker Desktop がインストールされていること
- 4GB以上の空きメモリ推奨（LLM実行用）

## 起動手順

1. **コンテナのビルドと起動**
   ```bash
   docker-compose up -d
   ```
   初回はDockerイメージのダウンロードとビルドに数分かかります。

2. **モデルのダウンロード**
   Ollamaコンテナが起動した後、モデルをダウンロードする必要があります。（初回のみ）
   
   ```bash
   docker-compose exec ollama ollama pull gemma2:2b
   ```
   ※ `llama3` など他のモデルを使う場合は `docker-compose.yml` の `OLLAMA_MODEL` 環境変数も変更してください。

3. **アプリにアクセス**
   ブラウザで http://localhost:8501 にアクセスしてください。

## 停止方法

```bash
docker-compose down
```

## 設定の変更

`docker-compose.yml` の `environment` セクションを変更することで、設定をカスタマイズできます。

```yaml
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434/api/generate
      - OLLAMA_MODEL=gemma2:2b
      - LARGE_AMOUNT_THRESHOLD=1000000
```

## GPUの使用（オプション）

NVIDIA GPUを使用する場合は、`docker-compose.yml` の `ollama` サービスのコメントアウトを外してください。
※ 事前に NVIDIA Container Toolkit のインストールが必要です。

```yaml
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```
