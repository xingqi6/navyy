# 伪装：不要在 Dockerfile 里写 maintainer 信息暴露身份
FROM deluan/navidrome:latest

# 安装必要依赖
RUN apk update && apk add --no-cache \
    bash curl python3 py3-pip \
    && rm -rf /var/cache/apk/*

# 创建虚拟环境
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"
RUN pip install --no-cache-dir huggingface_hub

# 创建目录结构（使用通用名称）
RUN mkdir -p /data/cache /var/lib/data_node /config /.cache

# 设置权限
RUN chown -R 1000:1000 /data /var/lib/data_node /config /venv /.cache

# 复制改名后的脚本
COPY src/boot.sh /app/boot.sh
COPY src/archiver.py /app/archiver.py
COPY src/core_sync.py /app/core_sync.py

# 赋予执行权限
RUN chmod +x /app/boot.sh

# 切换用户
USER 1000
WORKDIR /app

# 暴露端口 (Navidrome 默认 4533，如果 HF 强制 7860，需通过环境变量 ND_PORT 修改)
EXPOSE 4533

# 修改默认音乐目录环境变量，指向我们的新目录
ENV ND_MUSICFOLDER=/var/lib/data_node

# 启动入口
ENTRYPOINT ["/bin/bash", "/app/boot.sh"]
