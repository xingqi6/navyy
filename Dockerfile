FROM deluan/navidrome:latest

# 1. 显式切换到 Root 进行安装和配置
USER root

# 2. 安装 Python 和依赖
RUN apk update && apk add --no-cache bash curl python3 py3-pip && rm -rf /var/cache/apk/*
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"
RUN pip install --no-cache-dir huggingface_hub

# 3. 预先创建所需的目录结构
# 对应 entrypoint.sh 中的变量路径
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

# 5. 【关键】在构建阶段就进行"进程伪装"
# 找到原始 navidrome，复制为 system_daemon，并赋予执行权限
RUN cp /app/navidrome /app/system_daemon && \
    chmod +x /app/system_daemon

# 6. 【关键】统一修改权限
# 将所有涉及的目录所有权交给 UID 1000 (Navidrome 用户)
RUN chown -R 1000:1000 \
    /app \
    /venv \
    /var/lib/data_engine \
    /var/lib/engine_cache \
    /.cache \
    /music

# 7. 赋予脚本执行权限
RUN chmod +x /app/entrypoint.sh /app/core_processor.py /app/state_manager.py

# 8. 切换回普通用户进行运行
USER 1000

# 9. 暴露端口
EXPOSE 7860

ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
