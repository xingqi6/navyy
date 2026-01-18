#!/bin/bash

# ================= 变量配置 =================
MUSIC_ROOT=${MUSIC_DIR:-/music}
SYNC_SOURCES=${DATASET_MUSIC_NAME}
AUTH_TOKEN=${MUSIC_TOKEN}
BACKUP_REPO=${BACKUP_DATASET_ID}
BACKUP_CYCLE=${BACKUP_INTERVAL:-3600}
SYNC_CYCLE=${MUSIC_UPDATE_INTERVAL:-3600}

# 过滤配置
DOWNLOAD_FILTER=${ND_DOWNLOAD_FILTER:-"*"}
QUALITY_FILTER=${ND_QUALITY_FILTER:-"*"}

# 内部路径
INTERNAL_DATA="/var/lib/data_engine"
INTERNAL_CACHE="/var/lib/engine_cache"
FAKE_PROCESS_NAME="system_daemon"

# === Navidrome 核心配置 (解决报错的关键) ===
export ND_MUSICFOLDER="${MUSIC_ROOT}"
export ND_DATAFOLDER="${INTERNAL_DATA}"
export ND_CACHEFOLDER="${INTERNAL_CACHE}"
export ND_PORT=7860

# 1. 彻底关闭实时监控 (解决 Expression tree is too large)
export ND_ENABLEWATCHER=false 
# 2. 降低扫描频率到1小时 (避免下载时数据库死锁)
export ND_SCANSCHEDULE="@every 1h"
# 3. 降低日志噪音
export ND_LOGLEVEL="info"

# 扩展功能
export ND_LASTFM_APIKEY=${ND_LASTFM_APIKEY:-""}
export ND_LASTFM_SECRET=${ND_LASTFM_SECRET:-""}
export ND_SPOTIFY_ID=${ND_SPOTIFY_ID:-""}
export ND_SPOTIFY_SECRET=${ND_SPOTIFY_SECRET:-""}
export ND_ENABLESHARING=${ND_ENABLESHARING:-false}
export ND_BASEURL=${ND_BASEURL:-""}

# ================= 逻辑执行 =================

echo "[BOOT] System starting..."

# 【重要】清理旧文件，确保智能去重生效
echo "[BOOT] Cleaning up old media to apply smart deduplication..."
rm -rf "${MUSIC_ROOT:?}/"*

# 1. 激活环境
source /venv/bin/activate

# 2. 恢复备份
if [ -n "$BACKUP_REPO" ] && [ -n "$AUTH_TOKEN" ]; then
    echo "[BOOT] Restoring state..."
    python3 /app/state_manager.py download "$AUTH_TOKEN" "$BACKUP_REPO" "${INTERNAL_DATA}" || true
fi

# 3. 启动同步 (传入7个参数)
if [ -n "$SYNC_SOURCES" ] && [ -n "$AUTH_TOKEN" ]; then
    echo "[BOOT] Starting smart sync daemon..."
    python3 /app/core_processor.py "$SYNC_SOURCES" "$AUTH_TOKEN" "${MUSIC_ROOT}" "$SYNC_CYCLE" "false" "$DOWNLOAD_FILTER" "$QUALITY_FILTER" &
fi

# 4. 启动备份
if [ -n "$BACKUP_REPO" ] && [ -n "$AUTH_TOKEN" ]; then
    (
        while true; do
            sleep "${BACKUP_CYCLE}"
            python3 /app/state_manager.py upload "$AUTH_TOKEN" "$BACKUP_REPO" "${INTERNAL_DATA}"
        done
    ) &
fi

# 5. 启动伪装的主进程
TARGET_BIN="/app/${FAKE_PROCESS_NAME}"

if [ -f "$TARGET_BIN" ]; then
    echo "[BOOT] Daemon ready. Serving on 7860..."
    exec "$TARGET_BIN"
else
    exec /app/navidrome
fi
