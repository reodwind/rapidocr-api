FROM python:3.11.2-slim-buster

ENV DEBIAN_FRONTEND=noninteractive

# 设置工作目录
WORKDIR /app
    
# 安装运行环境
RUN set -eux; \
    pip install --no-cache-dir onnxruntime rapidocr; \
    pip install --no-cache-dir requests fastapi uvicorn python-multipart; \
    pip uninstall -y opencv-python; \
    pip install --no-cache-dir opencv-python-headless

RUN set -eux; \
    rapidocr check; \
    rapidocr config; \
    mv default_rapidocr.yaml config.yaml

# 将 entrypoint 脚本复制到镜像中
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 复制源代码到工作目录
COPY ./api/api.py .

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "api.py", "-ip", "0.0.0.0", "-p", "8080", "-workers", "2"]