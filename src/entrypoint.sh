#!/bin/bash

# ================= 变量处理区域 =================
# 1. 基础变量 (用户指定)
MUSIC_ROOT=${MUSIC_DIR:-/music}                   # 音乐目录
SYNC_SOURCES=${DATASET_MUSIC_NAME}                # 数据集 (支持逗号分隔)
AUTH_TOKEN=${MUSIC_TOKEN}                         # Token
BACKUP_REPO=${BACKUP_DATASET_ID}                  # 备份数据集
BACKUP_CYCLE=${BACKUP_INTERVAL:-3600}             # 备份间隔
SYNC_CYCLE=${MUSIC_UPDATE_INTERVAL:-3600}         # 同步间隔

# 2. 内部固定配置 (用户无需关心)
INTERNAL_DATA="/var/lib/data_engine"              # 数据库存放位置
INTERNAL_CACHE="/var/lib/engine_cache"            # 缓存位置
FAKE_PROCESS_NAME="system_daemon"                 # 伪装进程名

# 3. 导出 Navidrome 所需的环境变量
# 将用户填写的 ND_ 变量直接导出给进程
export ND_MUSICFOLDER="${MUSIC_ROOT}"
export ND_DATAFOLDER="${INTERNAL_DATA}"
export ND_CACHEFOLDER="${INTERNAL_CACHE}"
export ND_PORT=7860                               # HF 强制端口

# 导出额外的功能变量 (Last.fm, Spotify, Sharing)
export ND_LASTFM_APIKEY=${ND_LASTFM_APIKEY:-""}
export ND_LASTFM_SECRET=${ND_LASTFM_SECRET:-""}
export ND_SPOTIFY_ID=${ND_SPOTIFY_ID:-""}
export ND_SPOTIFY_SECRET=${ND_SPOTIFY_SECRET:-""}
export ND_ENABLESHARING=${ND_ENABLESHARING:-false}

# ================= 逻辑执行区域 =================

echo "[BOOT] Initializing System..."

# 1. 创建目录
mkdir -p "${INTERNAL_DATA}" "${INTERNAL_CACHE}" "${MUSIC_ROOT}" /.cache
chmod -R 777 "${INTERNAL_DATA}" "${INTERNAL_CACHE}" "${MUSIC_ROOT}" /.cache

# 2. 激活 Python 环境
source /venv/bin/activate

# 3. 恢复备份 (如果有配置)
if [ -n "$BACKUP_REPO" ] && [ -n "$AUTH_TOKEN" ]; then
    echo "[BOOT] Restoring state..."
    python3 /app/state_manager.py download "$AUTH_TOKEN" "$BACKUP_REPO" "${INTERNAL_DATA}"
fi

# 4. 启动多数据集同步 (后台运行)
if [ -n "$SYNC_SOURCES" ] && [ -n "$AUTH_TOKEN" ]; then
    echo "[BOOT] Starting sync daemon..."
    # 传入: 数据集列表, token, 音乐目录, 间隔
    python3 /app/core_processor.py "$SYNC_SOURCES" "$AUTH_TOKEN" "${MUSIC_ROOT}" "$SYNC_CYCLE" "false" &
fi

# 5. 启动自动备份 (后台运行)
if [ -n "$BACKUP_REPO" ] && [ -n "$AUTH_TOKEN" ]; then
    (
        while true; do
            sleep "${BACKUP_CYCLE}"
            python3 /app/state_manager.py upload "$AUTH_TOKEN" "$BACKUP_REPO" "${INTERNAL_DATA}"
        done
    ) &
fi

# 6. 伪装并启动主进程
ORIG_BIN=$(which navidrome || find /app -name navidrome -type f | head -1)

if [ -f "$ORIG_BIN" ]; then
    TARGET_BIN="/app/${FAKE_PROCESS_NAME}"
    cp "$ORIG_BIN" "$TARGET_BIN"
    chmod +x "$TARGET_BIN"
    echo "[BOOT] System ready."
    exec "$TARGET_BIN"
else
    echo "[FATAL] Binary not found."
    exit 1
fi
