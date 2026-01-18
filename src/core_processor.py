#!/usr/bin/env python3
# Obfuscated: Core Processor (Debug Version)
from huggingface_hub import HfApi, hf_hub_download
import os
import sys
import time
import json
import fnmatch
import shutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# === 配置区域 ===
DISK_SAFE_LIMIT_MB = 1024  # 1GB 保护
# =================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [SYNC] {msg}", flush=True)

def get_free_space_mb(folder):
    try:
        total, used, free = shutil.disk_usage(folder)
        return free // (1024 * 1024)
    except: return 999999

def match_rule(filename, patterns):
    """智能匹配逻辑"""
    if not patterns or patterns == "*" or patterns.strip() == "":
        return True
    
    # 统一转小写进行匹配，忽略大小写差异
    filename_lower = filename.lower()
    rules = [p.strip().lower() for p in patterns.split(',') if p.strip()]
    
    for rule in rules:
        if "*" in rule:
            # 通配符模式 (例如: *周杰伦*)
            if fnmatch.fnmatch(filename_lower, rule):
                return True
        else:
            # 纯文本包含模式 (例如: [320])
            if rule in filename_lower:
                return True
    return False

def get_filtered_files(api, repo_id, artist_patterns, quality_patterns):
    try:
        log(f"正在获取 {repo_id} 的文件列表...")
        all_files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
        
        # --- 🔍 调试核心：打印前 5 个文件看看长什么样 ---
        log("---------------- 调试信息：Dataset 文件名采样 ----------------")
        for i, sample in enumerate(all_files[:5]):
            log(f"样本 {i+1}: {sample}")
        log("-----------------------------------------------------------")
        # --------------------------------------------------------

        target_files = []
        rejected_sample = 0
        
        for f in all_files:
            # 排除非媒体文件
            if f.endswith(('.gitattributes', 'README.md', '.git', '.json')):
                continue

            # 1. 歌手匹配
            if not match_rule(f, artist_patterns):
                continue
            
            # 2. 音质匹配
            if not match_rule(f, quality_patterns):
                # 打印前 3 个因为音质被过滤掉的文件，方便排查
                if rejected_sample < 3:
                    log(f"[调试] 文件 '{f}' 通过了歌手过滤，但被音质规则 '{quality_patterns}' 过滤掉了。")
                    rejected_sample += 1
                continue
            
            target_files.append(f)
        
        log(f"过滤统计: 总文件 {len(all_files)} -> 目标文件 {len(target_files)}")
        return target_files
    except Exception as e:
        log(f"列表获取失败: {e}")
        return []

def download_single_file(repo_id, filename, token, target_root):
    free_mb = get_free_space_mb(target_root)
    if free_mb < DISK_SAFE_LIMIT_MB: return "DISK_FULL"
    try:
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="dataset",
            token=token,
            local_dir=target_root,
            local_dir_use_symlinks=False, 
            force_download=False
        )
        return "SUCCESS"
    except Exception as e:
        print(f"[ERROR] {filename}: {e}")
        return "ERROR"

def sync_repo(repo_id, token, root_dir, force=False, artist_filter="*", quality_filter="*"):
    safe_name = repo_id.replace("/", "_")
    target_dir = os.path.join(root_dir, safe_name)
    os.makedirs(target_dir, exist_ok=True)
    
    if get_free_space_mb(target_dir) < DISK_SAFE_LIMIT_MB:
        log(f"🛑 磁盘空间不足 {DISK_SAFE_LIMIT_MB}MB，停止下载。")
        return

    api = HfApi(token=token)
    files_to_download = get_filtered_files(api, repo_id, artist_filter, quality_filter)
    
    if not files_to_download:
        log("⚠️ 没有匹配的文件。请检查上方日志中的【文件名采样】和【过滤规则】是否一致。")
        return

    log(f"准备下载 {len(files_to_download)} 个文件...")
    
    success_count = 0
    disk_full_flag = False
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(download_single_file, repo_id, f, token, target_dir): f for f in files_to_download}
        total = len(files_to_download)
        for i, future in enumerate(as_completed(futures)):
            res = future.result()
            if res == "SUCCESS": success_count += 1
            elif res == "DISK_FULL": 
                disk_full_flag = True
                pass
            if i % 50 == 0: print(f"进度: {i}/{total}...", end="\r", flush=True)
                
    print(f"\n") 
    log(f"任务结束。成功: {success_count}/{len(files_to_download)}")
    if disk_full_flag: log("🛑 触发磁盘保护，部分下载已暂停。")

if __name__ == "__main__":
    if len(sys.argv) < 4: sys.exit(0)
    sources = [s.strip() for s in sys.argv[1].split(',') if s.strip()]
    token, root = sys.argv[2], sys.argv[3]
    interval = int(sys.argv[4])
    artist_filter = sys.argv[6] if len(sys.argv) > 6 else "*"
    quality_filter = sys.argv[7] if len(sys.argv) > 7 else "*"

    print(f"[DEBUG] 启动模式: 歌手='{artist_filter}', 音质='{quality_filter}'", flush=True)

    for s in sources: 
        sync_repo(s, token, root, force=True, artist_filter=artist_filter, quality_filter=quality_filter)

    log("进入监控模式...")
    while True:
        time.sleep(interval)
        for s in sources: 
            sync_repo(s, token, root, force=False, artist_filter=artist_filter, quality_filter=quality_filter)
