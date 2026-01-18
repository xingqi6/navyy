#!/usr/bin/env python3
# Obfuscated: Core Processor (Smart Filter & Disk Guard)
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
DISK_SAFE_LIMIT_MB = 1024  # 剩余空间低于 1024MB (1GB) 时停止下载
# =================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [SYNC] {msg}", flush=True)

def get_free_space_mb(folder):
    """获取指定目录所在磁盘的剩余空间(MB)"""
    try:
        total, used, free = shutil.disk_usage(folder)
        return free // (1024 * 1024)
    except:
        return 999999

def match_rule(filename, patterns):
    """
    智能匹配逻辑：
    1. 如果规则包含 '*'，使用 fnmatch 通配符匹配
    2. 如果规则不含 '*'，使用 字符串包含 匹配 (大小写不敏感)
    """
    if not patterns or patterns == "*":
        return True
    
    rules = [p.strip() for p in patterns.split(',') if p.strip()]
    for rule in rules:
        if "*" in rule:
            # 通配符模式 (例如: *周杰伦*)
            if fnmatch.fnmatch(filename, rule):
                return True
        else:
            # 纯文本包含模式 (例如: [320])
            if rule.lower() in filename.lower():
                return True
    return False

def get_filtered_files(api, repo_id, artist_patterns, quality_patterns):
    """双重过滤逻辑"""
    try:
        log(f"正在获取 {repo_id} 的文件列表...")
        all_files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
        
        target_files = []
        for f in all_files:
            # 排除非媒体文件
            if f.endswith(('.gitattributes', 'README.md', '.git', '.json')):
                continue

            # 1. 第一层：歌手/路径过滤
            if not match_rule(f, artist_patterns):
                continue
            
            # 2. 第二层：音质过滤 (必须同时满足)
            if not match_rule(f, quality_patterns):
                continue
            
            target_files.append(f)
        
        log(f"过滤统计: 总文件 {len(all_files)} -> 目标文件 {len(target_files)}")
        return target_files
    except Exception as e:
        log(f"列表获取失败: {e}")
        return []

def download_single_file(repo_id, filename, token, target_root):
    """下载单个文件（含磁盘检查）"""
    # 1. 磁盘检查 (熔断机制)
    free_mb = get_free_space_mb(target_root)
    if free_mb < DISK_SAFE_LIMIT_MB:
        return "DISK_FULL"

    # 2. 执行下载
    try:
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="dataset",
            token=token,
            local_dir=target_root,
            local_dir_use_symlinks=False, # 强制物理文件
            force_download=False # 利用缓存
        )
        return "SUCCESS"
    except Exception as e:
        print(f"[ERROR] {filename}: {e}")
        return "ERROR"

def sync_repo(repo_id, token, root_dir, force=False, artist_filter="*", quality_filter="*"):
    safe_name = repo_id.replace("/", "_")
    target_dir = os.path.join(root_dir, safe_name)
    os.makedirs(target_dir, exist_ok=True)
    
    api = HfApi(token=token)
    
    # 1. 检查磁盘初始状态
    if get_free_space_mb(target_dir) < DISK_SAFE_LIMIT_MB:
        log(f"⚠️ 警告: 磁盘空间已不足 {DISK_SAFE_LIMIT_MB}MB，跳过下载任务！请清理空间。")
        return

    # 2. 计算文件列表
    files_to_download = get_filtered_files(api, repo_id, artist_filter, quality_filter)
    
    if not files_to_download:
        log("没有匹配的文件，跳过。")
        return

    log(f"准备并发下载 {len(files_to_download)} 个文件...")
    
    # 3. 多线程下载
    success_count = 0
    disk_full_flag = False
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(download_single_file, repo_id, f, token, target_dir): f for f in files_to_download}
        
        total = len(files_to_download)
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            
            if result == "SUCCESS":
                success_count += 1
            elif result == "DISK_FULL":
                disk_full_flag = True
                # 既然满了，就不等后面的了，虽然executor还会跑完当前的
                # 我们可以选择break，但为了优雅关闭，让它跑完队列里的任务但快速返回
                pass 

            if i % 20 == 0:
                print(f"进度: {i}/{total} (成功:{success_count})", end="\r", flush=True)
                if disk_full_flag:
                    print("\n")
                    log("🛑 紧急停止: 磁盘空间已达到临界值！下载已中断。")
                    executor.shutdown(wait=False) # 尝试停止
                    break
                
    print(f"\n") 
    log(f"任务结束。成功下载: {success_count}/{len(files_to_download)}")
    
    if disk_full_flag:
        log("⚠️ 注意: 部分歌曲因磁盘满而未下载。请修改过滤规则减少下载量。")

if __name__ == "__main__":
    if len(sys.argv) < 4: sys.exit(0)
    
    sources = [s.strip() for s in sys.argv[1].split(',') if s.strip()]
    token = sys.argv[2]
    root = sys.argv[3]
    interval = int(sys.argv[4])
    artist_filter = sys.argv[6] if len(sys.argv) > 6 else "*"
    quality_filter = sys.argv[7] if len(sys.argv) > 7 else "*"

    print(f"[DEBUG] 启动模式: 歌手='{artist_filter}', 音质='{quality_filter}'", flush=True)
    print(f"[DEBUG] 磁盘安全阈值: {DISK_SAFE_LIMIT_MB} MB")

    # 首次运行
    for s in sources: 
        sync_repo(s, token, root, force=True, artist_filter=artist_filter, quality_filter=quality_filter)

    # 循环
    log("进入守护模式...")
    while True:
        time.sleep(interval)
        # 守护模式下是否继续同步取决于你的需求，为防爆盘，建议只在重启时全量同步
        # 或者保留下面这行，它会检测新文件，如果磁盘满了会自动停止
        for s in sources: 
            sync_repo(s, token, root, force=False, artist_filter=artist_filter, quality_filter=quality_filter)
