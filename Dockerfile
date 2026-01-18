FROM deluan/navidrome:latest

# 1. 切换到 root 进行安装和配置 (关键步骤)
USER root

# 2. 安装 Python 和依赖
RUN apk update && apk add --no-cache bash curl python3 py3-pip && rm -rf /var/cache/apk/*
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"
RUN pip install --no-cache-dir huggingface_hub

# 3. 预先创建所有需要的目录
# 直接在这里建立，不要在脚本里建
RUN mkdir -p /var/lib/data_engine \
    /var/lib/engine_cache \
    /.cache \
    /music \
    /app

# 4. 复制 Python 脚本
WORKDIR /app
COPY src/core_processor.py /app/core_processor.py
COPY src/state_manager.py /app/state_manager.py
COPY src/entrypoint.sh /app/entrypoint.sh

# 5. 【关键】在构建阶段完成进程伪装
# 直接把 navidrome 复制一份叫 system_daemon
RUN cp /app/navidrome /app/system_daemon && \
    chmod +x /app/system_daemon

# 6. 【关键】统一修改权限
# 把所有目录的所有权都交给 id 为 1000 的用户 (Navidrome 默认用户)
RUN chown -R 1000:1000 \
    /app \
    /venv \
    /var/lib/data_engine \
    /var/lib/engine_cache \
    /.cache \
    /music

# 7. 给脚本执行权限
RUN chmod +x /app/entrypoint.sh /app/core_processor.py /app/state_manager.py

# 8. 切换回普通用户 (为了安全和HF要求)
USER 1000

# 9. 暴露端口
EXPOSE 7860

ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
