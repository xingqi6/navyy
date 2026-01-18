#!/bin/bash

# ================= 配置区域 =================
# 1. 核心路径配置 (伪装成通用数据引擎)
STORAGE_ROOT="/var/lib/data_engine"  # 数据库位置
CACHE_ROOT="/var/lib/engine_cache"   # 缓存位置
# 如果用户设置了 MUSIC_DIR，则使用用户的，否则使用默认
MUSIC_ROOT=${MUSIC_DIR:-/var/lib/media_store}

# 2. 同步与备份配置
SYNC_SOURCES=${DATASET_MUSIC_NAME}   # 格式：user/repo1,user/repo2
AUTH_TOKEN=${MUSIC_TOKEN}            # HF Token
BACKUP_REPO=${BACKUP_DATASET_ID}     # 备份用 Dataset
SYNC_INTERVAL=${MUSIC_UPDATE_INTERVAL:-3600}
BACKUP_INTERVAL=${BACKUP_INTERVAL:-3600}

# 3. 进程伪装名称
FAKE_PROCESS_NAME="system_daemon"
# ===========================================

echo "[BOOT] System Initializing..."
echo "[BOOT] Loading configuration..."

# --- 核心：环境变量透传区域 ---
# 将用户在 HF 设置的变量明确导出，确保内核能读取
# 虽然 Docker 默认会透传，但显式声明更安全，方便调试

# 基础设置
export ND_DATAFOLDER="${STORAGE_ROOT}"
export ND_MUSICFOLDER="${MUSIC_ROOT}"
export ND_CACHEFOLDER="${CACHE_ROOT}"
export ND_PORT=${ND_PORT:-7860}  # HF 强制端口
export ND_BASEURL=${ND_BASEURL:-""} # 反代地址

# 第三方集成 (Last.fm / Spotify)
export ND_LASTFM_APIKEY=${ND_LASTFM_APIKEY:-""}
export ND_LASTFM_SECRET=${ND_LASTFM_SECRET:-""}
export ND_SPOTIFY_ID=${ND_SPOTIFY_ID:-""}
export ND_SPOTIFY_SECRET=${ND_SPOTIFY_SECRET:-""}

# 功能开关
export ND_ENABLESHARING=${ND_ENABLESHARING:-false} # 是否开启分享
export ND_SCANSCHEDULE=${ND_SCANSCHEDULE:-"@every 1h"} # 扫描频率
export ND_LOGLEVEL=${ND_LOGLEVEL:-"info"} 

# -----------------------------------

# 1. 目录准备
mkdir -p ${STORAGE_ROOT} ${CACHE_ROOT} ${MUSIC_ROOT} /.cache
chmod -R 777 ${STORAGE_ROOT} ${CACHE_ROOT} ${MUSIC_ROOT} /.cache

# 2. 激活虚拟环境
source /venv/bin/activate

# 3. 恢复状态 (Archive Restore)
if [ -n "$BACKUP_REPO" ] && [ -n "$AUTH_TOKEN" ]; then
    echo "[BOOT] Checking integrity (Restore)..."
    python3 /app/state_manager.py download "$AUTH_TOKEN" "$BACKUP_REPO" "${STORAGE_ROOT}"
fi

# 4. 启动多源同步 (Resource Sync) - 后台运行
if [ -n "$SYNC_SOURCES" ] && [ -n "$AUTH_TOKEN" ]; then
    echo "[BOOT] Starting I/O processor (Sync)..."
    # 传入: 数据集列表, token, 音乐目录, 间隔, 是否强制
    python3 /app/core_processor.py "$SYNC_SOURCES" "$AUTH_TOKEN" "${MUSIC_ROOT}" "$SYNC_INTERVAL" "false" &
fi

# 5. 启动自动备份 (State Backup) - 后台运行
if [ -n "$BACKUP_REPO" ] && [ -n "$AUTH_TOKEN" ]; then
    echo "[BOOT] Initializing backup scheduler..."
    (
        while true; do
            sleep "${BACKUP_INTERVAL}"
            python3 /app/state_manager.py upload "$AUTH_TOKEN" "$BACKUP_REPO" "${STORAGE_ROOT}"
        done
    ) &
fi

# 6. 核心：进程伪装与启动
ORIG_BIN=$(which navidrome || find /app -name navidrome -type f | head -1)

if [ -f "$ORIG_BIN" ]; then
    # 复制并重命名二进制文件
    TARGET_BIN="/app/${FAKE_PROCESS_NAME}"
    cp "$ORIG_BIN" "$TARGET_BIN"
    chmod +x "$TARGET_BIN"
    
    echo "[BOOT] Launching daemon [PID $$]..."
    
    # 启动伪装后的进程
    # exec 会替换当前 shell 进程，让 system_daemon 成为 PID 1 (或主进程)
    exec "$TARGET_BIN"
else
    echo "[FATAL] Engine binary missing."
    exit 1
fi
