# 洞察织机 InsightLoom — 自托管镜像
# 构建: docker build -t insightloom .
# 运行: docker run -p 8300:8300 -v insightloom_data:/app/data -v insightloom_vault:/app/vault insightloom
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 依赖层(单独拷贝,充分利用缓存)
COPY requirements.txt .
RUN pip install -r requirements.txt

# 应用层
COPY server ./server
COPY web ./web
COPY scripts ./scripts
COPY README.md ./

# 运行期数据(SQLite/Chroma 索引/嵌入模型缓存)与用户知识库都放卷里
# (嵌入模型缓存路径由 server/retrieval.py 重定向到 /app/data/chroma_models)
VOLUME ["/app/data", "/app/vault"]

EXPOSE 8300
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8300"]
