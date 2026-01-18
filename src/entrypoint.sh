#!/bin/bash

# ================= 变量配置 =================
MUSIC_ROOT=${MUSIC_DIR:-/music}
SYNC_SOURCES=${DATASET_MUSIC_NAME}
AUTH_TOKEN=${MUSIC_TOKEN}
BACKUP_REPO=${BACKUP_DATASET_ID}
BACKUP_CYCLE=${BACKUP_INTERVAL:-3600}
SYNC_CYCLE=${MUSIC_UPDATE_INTERVAL:-3600}

# 【新增】过滤规则，默认下载所有 ("*")
# 用户可以在 HF 环境变量里填 "周杰伦*,陈奕迅*"
DOWNLOAD_FILTER=${ND_DOWNLOAD_FILTER:-"*"}

# 内部路径
INTERNAL_DATA="/var/lib/data_engine"
INTERNAL_CACHE="/var/lib/engine_cache"
FAKE_PROCESS_NAME="system_daemon"

# 导出变量
export ND_MUSICFOLDER="${MUSIC_ROOT}"
export ND_DATAFOLDER="${INTERNAL_DATA}"
export ND_CACHEFOLDER="${INTERNAL_CACHE}"
export ND_PORT=7860
# 优化：关闭文件监控，避免大量文件导致报错
export ND_ENABLEWATCHER=false 
export ND_SCANSCHEDULE="@every 10m"

export ND_LASTFM_APIKEY=${ND_LASTFM_APIKEY:-""}
export ND_LASTFM_SECRET=${ND_LASTFM_SECRET:-""}
export ND_SPOTIFY_ID=${ND_SPOTIFY_ID:-""}
export ND_SPOTIFY_SECRET=${ND_SPOTIFY_SECRET:-""}
export ND_ENABLESHARING=${ND_ENABLESHARING:-false}

# ================= 逻辑执行 =================

echo "[BOOT] System starting..."

# 1. 激活环境
source /venv/bin/activate

# 2. 恢复备份
if [ -n "$BACKUP_REPO" ] && [ -n "$AUTH_TOKEN" ]; then
    echo "[BOOT] Restoring state..."
    python3 /app/state_manager.py download "$AUTH_TOKEN" "$BACKUP_REPO" "${INTERNAL_DATA}" || true
fi

# 3. 启动同步 (传入过滤参数)
if [ -n "$SYNC_SOURCES" ] && [ -n "$AUTH_TOKEN" ]; then
    echo "[BOOT] Starting sync daemon with filter: $DOWNLOAD_FILTER"
    # 注意：这里多传了一个参数 "$DOWNLOAD_FILTER"
    python3 /app/core_processor.py "$SYNC_SOURCES" "$AUTH_TOKEN" "${MUSIC_ROOT}" "$SYNC_CYCLE" "false" "$DOWNLOAD_FILTER" &
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

# 5. 启动主进程
TARGET_BIN="/app/${FAKE_PROCESS_NAME}"

if [ -f "$TARGET_BIN" ]; then
    echo "[BOOT] Daemon ready. Serving on 7860..."
    exec "$TARGET_BIN"
else
    echo "[FATAL] Binary not found."
    exit 1
fi
