FROM deluan/navidrome:latest

# 安装环境
RUN apk update && apk add --no-cache bash curl python3 py3-pip && rm -rf /var/cache/apk/*

# 准备 Python 依赖
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"
RUN pip install --no-cache-dir huggingface_hub

# 复制脚本
WORKDIR /app
COPY src/core_processor.py /app/core_processor.py
COPY src/state_manager.py /app/state_manager.py
COPY src/entrypoint.sh /app/entrypoint.sh

# 权限
RUN chmod +x /app/entrypoint.sh /app/core_processor.py /app/state_manager.py

# 用户与端口
USER 1000
EXPOSE 7860

ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
