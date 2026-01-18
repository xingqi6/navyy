# 基础镜像
FROM deluan/navidrome:latest

# 1. 安装 Python 环境
RUN apk update && apk add --no-cache \
    bash \
    curl \
    python3 \
    py3-pip \
    && rm -rf /var/cache/apk/*

# 2. 准备虚拟环境和依赖
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"
RUN pip install --no-cache-dir huggingface_hub

# 3. 创建目录结构
WORKDIR /app

# 4. 复制并安装脚本
COPY src/core_processor.py /app/core_processor.py
COPY src/state_manager.py /app/state_manager.py
COPY src/entrypoint.sh /app/entrypoint.sh

# 5. 权限设置
RUN chmod +x /app/entrypoint.sh /app/core_processor.py /app/state_manager.py

# 6. 端口设置 (Hugging Face 默认端口)
ENV ND_PORT=7860
EXPOSE 7860

# 7. 切换用户 (Navidrome 镜像默认 UID 1000)
USER 1000

# 8. 启动
ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
