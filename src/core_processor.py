#!/usr/bin/env python3
# Obfuscated: Core Processor
from huggingface_hub import snapshot_download, HfApi
import os
import sys
import time
import json
import fnmatch
from datetime import datetime

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [SYNC] {msg}", flush=True)

def check_files(target_dir):
    """调试函数：检查目录下是否有文件"""
    log(f"--- 正在检查目录: {target_dir} ---")
    try:
        count = 0
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                count += 1
                if count <= 5: # 只打印前5个文件证明存在
                    log(f"发现文件: {os.path.join(root, file)}")
        log(f"--- 目录检查结束，总计文件数: {count} ---")
        return count
    except Exception as e:
        log(f"目录检查出错: {e}")
        return 0

def get_filtered_files(api, repo_id, artist_patterns, quality_patterns):
    try:
        log(f"正在获取 {repo_id} 的文件列表...")
        all_files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
        
        # 1. 歌手过滤
        if artist_patterns and artist_patterns != "*":
            artist_rules = [p.strip() for p in artist_patterns.split(',') if p.strip()]
            step1_files = [f for f in all_files if any(fnmatch.fnmatch(f, rule) for rule in artist_rules)]
        else:
            step1_files = all_files

        # 2. 音质过滤
        if quality_patterns and quality_patterns != "*":
            quality_rules = [p.strip() for p in quality_patterns.split(',') if p.strip()]
            final_files = [f for f in step1_files if any(fnmatch.fnmatch(f, rule) for rule in quality_rules)]
            log(f"应用音质过滤: {quality_rules}")
        else:
            final_files = step1_files

        if ".sync_meta" not in final_files:
            final_files.append(".sync_meta")
            
        log(f"过滤结果: {len(all_files)} -> {len(final_files)} 文件")
        return final_files
    except Exception as e:
        log(f"列表获取失败: {e}")
        return None

def sync_repo(repo_id, token, root_dir, force=False, artist_filter="*", quality_filter="*"):
    safe_name = repo_id.replace("/", "_")
    target_dir = os.path.join(root_dir, safe_name)
    os.makedirs(target_dir, exist_ok=True)
    
    # 强制跳过 SHA 检查，因为过滤规则可能变了，必须重新运行下载逻辑
    # 我们依赖 allow_patterns 来决定下载什么
    
    api = HfApi(token=token)
    allow_patterns = None
    if artist_filter != "*" or quality_filter != "*":
        allow_patterns = get_filtered_files(api, repo_id, artist_filter, quality_filter)
        if not allow_patterns:
            log(f"警告: {repo_id} 过滤后无文件。")
            return
    
    log(f"开始同步: {repo_id}")
    
    try:
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            local_dir=target_dir,
            token=token,
            ignore_patterns=[".git*", "README*"],
            allow_patterns=allow_patterns,
            local_dir_use_symlinks=False  # <---【核心修复】强制复制文件，不使用软链接！
        )
        
        log(f"同步指令完成，正在验证文件...")
        file_count = check_files(target_dir) # 立即检查文件是否存在
        
        if file_count > 0:
            log(f"成功: 资源 {safe_name} 已就绪，共 {file_count} 个文件。")
        else:
            log(f"严重警告: 同步指令结束但目录下没有文件！")

    except Exception as e:
        log(f"同步错误: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 4: sys.exit(0)
    
    sources = [s.strip() for s in sys.argv[1].split(',') if s.strip()]
    token = sys.argv[2]
    root = sys.argv[3]
    interval = int(sys.argv[4])
    artist_filter = sys.argv[6] if len(sys.argv) > 6 else "*"
    quality_filter = sys.argv[7] if len(sys.argv) > 7 else "*"

    print(f"[DEBUG] 启动参数: 歌手='{artist_filter}', 音质='{quality_filter}'", flush=True)

    # 首次运行
    for s in sources: 
        sync_repo(s, token, root, force=True, artist_filter=artist_filter, quality_filter=quality_filter)

    # 循环
    while True:
        time.sleep(interval)
        for s in sources: 
            sync_repo(s, token, root, force=False, artist_filter=artist_filter, quality_filter=quality_filter)
