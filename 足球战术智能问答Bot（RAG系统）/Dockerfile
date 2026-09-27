# File: Dockerfile
# 足球战术智能问答 RAG 系统镜像（API 与前端共用，由 docker-compose 覆盖启动命令）
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_ENDPOINT=https://hf-mirror.com

# 先安装 CPU 版 torch（镜像体积更小、启动更快），再安装其余依赖以利用层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000 8501

# 默认启动 API 服务；前端服务由 docker-compose 指定 streamlit 命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
