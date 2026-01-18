#!/usr/bin/env python3
# Obfuscated: Core Processor
from huggingface_hub import HfApi, hf_hub_download
import os
import sys
import time
import json
import fnmatch
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [SYNC] {msg}", flush=True)

def get_filtered_files(api, repo_id, artist_patterns, quality_patterns):
    """双重过滤逻辑：先歌手，后音质"""
    try:
        log(f"正在获取 {repo_id} 的文件列表...")
        all_files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
        
        # 1. 歌手/路径过滤
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

        # 排除非音乐文件
        final_files = [f for f in final_files if not f.endswith(('.gitattributes', 'README.md', '.git'))]
        
        log(f"过滤结果: 从 {len(all_files)} -> {len(final_files)} 个目标文件")
        return final_files
    except Exception as e:
        log(f"列表获取失败: {e}")
        return []

def download_single_file(repo_id, filename, token, target_root):
    """下载单个文件的原子操作"""
    try:
        # local_dir 会自动保持目录结构
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="dataset",
            token=token,
            local_dir=target_root,
            local_dir_use_symlinks=False, # 强制物理文件，防止软链接失效
            force_download=False # 利用缓存，不重复下载流量
        )
        return True
    except Exception as e:
        print(f"[ERROR] 下载失败 {filename}: {e}")
        return False

def sync_repo(repo_id, token, root_dir, force=False, artist_filter="*", quality_filter="*"):
    safe_name = repo_id.replace("/", "_")
    target_dir = os.path.join(root_dir, safe_name)
    os.makedirs(target_dir, exist_ok=True)
    
    api = HfApi(token=token)
    
    # 1. 计算文件列表
    files_to_download = get_filtered_files(api, repo_id, artist_filter, quality_filter)
    
    if not files_to_download:
        log("没有匹配的文件，跳过下载。")
        return

    # 2. 写入元数据 (可选)
    meta_path = os.path.join(target_dir, ".sync_meta")
    if not os.path.exists(meta_path):
        with open(meta_path, "w") as f: json.dump({"status": "filtered"}, f)

    log(f"准备并发下载 {len(files_to_download)} 个文件到 {target_dir} ...")
    
    # 3. 多线程并发下载 (核心修复)
    # 使用 8 线程并发，既快又稳，直接把文件写到硬盘
    success_count = 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(download_single_file, repo_id, f, token, target_dir): f for f in files_to_download}
        
        # 简单的进度条
        total = len(files_to_download)
        for i, future in enumerate(as_completed(futures)):
            if future.result():
                success_count += 1
            if i % 50 == 0:
                print(f"进度: {i}/{total}...", end="\r", flush=True)
                
    print(f"\n") # 换行
    log(f"下载任务结束。成功: {success_count}/{len(files_to_download)}")
    
    # 4. 最终核验
    actual_files = 0
    for r, d, f in os.walk(target_dir):
        actual_files += len(f)
    log(f"硬盘实际文件数核验: {actual_files}")

if __name__ == "__main__":
    # 参数处理
    if len(sys.argv) < 4: sys.exit(0)
    
    sources = [s.strip() for s in sys.argv[1].split(',') if s.strip()]
    token = sys.argv[2]
    root = sys.argv[3]
    interval = int(sys.argv[4])
    artist_filter = sys.argv[6] if len(sys.argv) > 6 else "*"
    quality_filter = sys.argv[7] if len(sys.argv) > 7 else "*"

    print(f"[DEBUG] 启动模式: 歌手='{artist_filter}', 音质='{quality_filter}'", flush=True)

    # 首次运行 (强制执行)
    for s in sources: 
        sync_repo(s, token, root, force=True, artist_filter=artist_filter, quality_filter=quality_filter)

    # 循环 (Navidrome 需要长期运行，这里保持挂起，或者定期检查)
    log("初次同步完成，进入监控模式...")
    while True:
        time.sleep(interval)
        # 循环中可以根据需求决定是否再次全量扫描，为省流可注释掉下面
        # for s in sources: sync_repo(...)
