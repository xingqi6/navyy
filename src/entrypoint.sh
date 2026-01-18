#!/bin/bash

# ================= 变量配置 =================
# 1. 基础变量
MUSIC_ROOT=${MUSIC_DIR:-/music}
SYNC_SOURCES=${DATASET_MUSIC_NAME}
AUTH_TOKEN=${MUSIC_TOKEN}
BACKUP_REPO=${BACKUP_DATASET_ID}
BACKUP_CYCLE=${BACKUP_INTERVAL:-3600}
SYNC_CYCLE=${MUSIC_UPDATE_INTERVAL:-3600}

# 2. 内部路径 (必须与 Dockerfile 创建的一致)
INTERNAL_DATA="/var/lib/data_engine"
INTERNAL_CACHE="/var/lib/engine_cache"
FAKE_PROCESS_NAME="system_daemon"

# 3. 导出环境变量给 Navidrome
export ND_MUSICFOLDER="${MUSIC_ROOT}"
export ND_DATAFOLDER="${INTERNAL_DATA}"
export ND_CACHEFOLDER="${INTERNAL_CACHE}"
export ND_PORT=7860

# 扩展变量
export ND_LASTFM_APIKEY=${ND_LASTFM_APIKEY:-""}
export ND_LASTFM_SECRET=${ND_LASTFM_SECRET:-""}
export ND_SPOTIFY_ID=${ND_SPOTIFY_ID:-""}
export ND_SPOTIFY_SECRET=${ND_SPOTIFY_SECRET:-""}
export ND_ENABLESHARING=${ND_ENABLESHARING:-false}

# ================= 逻辑执行 =================

echo "[BOOT] System starting..."

# 1. 激活 Python 环境
source /venv/bin/activate

# 2. 恢复备份
if [ -n "$BACKUP_REPO" ] && [ -n "$AUTH_TOKEN" ]; then
    echo "[BOOT] Restoring state..."
    # 加上 || true 防止没有备份时报错退出
    python3 /app/state_manager.py download "$AUTH_TOKEN" "$BACKUP_REPO" "${INTERNAL_DATA}" || true
fi

# 3. 启动同步 (后台)
if [ -n "$SYNC_SOURCES" ] && [ -n "$AUTH_TOKEN" ]; then
    echo "[BOOT] Starting sync daemon..."
    python3 /app/core_processor.py "$SYNC_SOURCES" "$AUTH_TOKEN" "${MUSIC_ROOT}" "$SYNC_CYCLE" "false" &
fi

# 4. 启动备份 (后台)
if [ -n "$BACKUP_REPO" ] && [ -n "$AUTH_TOKEN" ]; then
    (
        while true; do
            sleep "${BACKUP_CYCLE}"
            python3 /app/state_manager.py upload "$AUTH_TOKEN" "$BACKUP_REPO" "${INTERNAL_DATA}"
        done
    ) &
fi

# 5. 启动伪装的主进程
# 注意：这里直接运行 Dockerfile 里准备好的文件
TARGET_BIN="/app/${FAKE_PROCESS_NAME}"

if [ -f "$TARGET_BIN" ]; then
    echo "[BOOT] Daemon ready. Serving on 7860..."
    exec "$TARGET_BIN"
else
    echo "[FATAL] Binary not found at $TARGET_BIN"
    # 如果伪装失败，尝试运行原始文件（保底）
    if [ -f "/app/navidrome" ]; then
        echo "[WARN] Fallback to original binary"
        exec /app/navidrome
    else
        exit 1
    fi
fi
