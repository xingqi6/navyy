#!/bin/bash

# ================= 配置区域 =================
# 将 Navidrome 的数据存储位置重定向到通用目录名
STORAGE_ROOT="/var/lib/data_engine"
CACHE_ROOT="/var/lib/engine_cache"
MUSIC_ROOT=${MUSIC_DIR:-/var/lib/media_store}

# 环境变量映射
SYNC_SOURCES=${DATASET_MUSIC_NAME}   # 你的多个数据集，逗号分隔
AUTH_TOKEN=${MUSIC_TOKEN}            # HF Token
BACKUP_REPO=${BACKUP_DATASET_ID}     # 备份数据集
SYNC_INTERVAL=${MUSIC_UPDATE_INTERVAL:-3600}
BACKUP_INTERVAL=${BACKUP_INTERVAL:-3600}

# 进程伪装名称 (看起来像系统进程)
FAKE_PROCESS_NAME="system_daemon"
# ===========================================

echo "[BOOT] System Initializing..."

# 1. 目录准备
mkdir -p ${STORAGE_ROOT} ${CACHE_ROOT} ${MUSIC_ROOT} /.cache
# 确保 Navidrome (作为普通用户) 有权限写入
chmod -R 777 ${STORAGE_ROOT} ${CACHE_ROOT} ${MUSIC_ROOT} /.cache

# 2. 激活虚拟环境
source /venv/bin/activate

# 3. 恢复状态 (如果配置了)
if [ -n "$BACKUP_REPO" ] && [ -n "$AUTH_TOKEN" ]; then
    echo "[BOOT] Checking integrity..."
    python3 /app/state_manager.py download "$AUTH_TOKEN" "$BACKUP_REPO" "${STORAGE_ROOT}"
fi

# 4. 启动多源同步 (后台运行)
if [ -n "$SYNC_SOURCES" ] && [ -n "$AUTH_TOKEN" ]; then
    echo "[BOOT] Starting I/O processor..."
    # 传入 sources, token, 目标目录, 间隔, 是否强制
    python3 /app/core_processor.py "$SYNC_SOURCES" "$AUTH_TOKEN" "${MUSIC_ROOT}" "$SYNC_INTERVAL" "false" &
fi

# 5. 启动自动备份 (后台运行)
if [ -n "$BACKUP_REPO" ] && [ -n "$AUTH_TOKEN" ]; then
    (
        while true; do
            sleep "${BACKUP_INTERVAL}"
            python3 /app/state_manager.py upload "$AUTH_TOKEN" "$BACKUP_REPO" "${STORAGE_ROOT}"
        done
    ) &
fi

# 6. 核心：进程混淆与启动
# 查找原始 navidrome 二进制文件
ORIG_BIN=$(which navidrome || find /app -name navidrome -type f | head -1)

if [ -f "$ORIG_BIN" ]; then
    # 复制为伪装名称
    TARGET_BIN="/app/${FAKE_PROCESS_NAME}"
    cp "$ORIG_BIN" "$TARGET_BIN"
    chmod +x "$TARGET_BIN"
    
    echo "[BOOT] Launching daemon..."
    
    # 关键：设置 Navidrome 需要的环境变量指向我们的新路径
    export ND_DATAFOLDER="${STORAGE_ROOT}"
    export ND_MUSICFOLDER="${MUSIC_ROOT}"
    export ND_CACHEFOLDER="${CACHE_ROOT}"
    
    # HF 强制端口 7860，Navidrome 默认 4533，这里通过 ENV 覆盖
    # 如果你在 Dockerfile 没写 ND_PORT，这里必须写
    export ND_PORT=${ND_PORT:-7860} 
    
    # 启动伪装后的进程
    exec "$TARGET_BIN"
else
    echo "[FATAL] Engine binary missing."
    exit 1
fi
