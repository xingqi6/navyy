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

def get_filtered_files(api, repo_id, artist_patterns, quality_patterns):
    """
    获取远程文件列表，并进行双重过滤（歌手 AND 音质）
    """
    try:
        log(f"正在获取 {repo_id} 的文件列表以进行精确过滤...")
        # 获取所有文件列表
        all_files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
        
        # 1. 歌手/路径过滤 (OR 逻辑)
        if artist_patterns and artist_patterns != "*":
            artist_rules = [p.strip() for p in artist_patterns.split(',') if p.strip()]
            # 只要匹配任意一个歌手规则即可
            step1_files = [f for f in all_files if any(fnmatch.fnmatch(f, rule) for rule in artist_rules)]
        else:
            step1_files = all_files

        # 2. 音质过滤 (OR 逻辑，但在 Step1 的基础上进行，所以整体是 AND)
        if quality_patterns and quality_patterns != "*":
            quality_rules = [p.strip() for p in quality_patterns.split(',') if p.strip()]
            # 只要匹配任意一个音质规则即可
            final_files = [f for f in step1_files if any(fnmatch.fnmatch(f, rule) for rule in quality_rules)]
            log(f"应用音质过滤: {quality_rules}")
        else:
            final_files = step1_files

        # 总是包含元数据文件
        if ".sync_meta" not in final_files:
            final_files.append(".sync_meta")
            
        log(f"过滤结果: 从 {len(all_files)} 个文件精简到 {len(final_files)} 个文件")
        return final_files
    except Exception as e:
        log(f"获取文件列表失败: {e}")
        return None

def sync_repo(repo_id, token, root_dir, force=False, artist_filter="*", quality_filter="*"):
    safe_name = repo_id.replace("/", "_")
    target_dir = os.path.join(root_dir, safe_name)
    os.makedirs(target_dir, exist_ok=True)
    
    api = HfApi(token=token)
    
    # --- 元数据检查 ---
    meta_path = os.path.join(target_dir, ".sync_meta")
    remote_sha = ""
    try:
        remote_info = api.repo_info(repo_id=repo_id, repo_type="dataset")
        remote_sha = remote_info.sha
    except: pass

    local_sha = ""
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                local_sha = json.load(f).get("sha", "")
        except: pass

    # 如果启用了过滤，建议忽略SHA检查，强制运行一遍过滤逻辑
    # 只要不是全量下载，我们就不跳过，防止用户改了过滤规则但SHA没变
    skip_check = (artist_filter == "*" and quality_filter == "*")
    if skip_check and not force and local_sha == remote_sha and remote_sha != "":
        log(f"资源 {safe_name} 无需更新")
        return

    # --- 计算下载列表 ---
    # 如果有任意过滤条件，就进行精确计算
    allow_patterns = None
    if artist_filter != "*" or quality_filter != "*":
        allow_patterns = get_filtered_files(api, repo_id, artist_filter, quality_filter)
        if not allow_patterns:
            log(f"警告: 过滤后没有找到任何文件，跳过下载。")
            return
    
    log(f"开始同步: {repo_id} (Filter: Artist={artist_filter}, Quality={quality_filter})")
    
    try:
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            local_dir=target_dir,
            token=token,
            ignore_patterns=[".git*", "README*"],
            allow_patterns=allow_patterns # 传入精确计算后的文件列表
        )
        
        if remote_sha:
            with open(meta_path, "w") as f:
                json.dump({"sha": remote_sha}, f)
        log(f"同步完成: {safe_name}")
    except Exception as e:
        log(f"同步错误: {e}")

if __name__ == "__main__":
    # 参数: sources token dir interval force artist_filter quality_filter
    if len(sys.argv) < 4: sys.exit(0)
    
    sources = [s.strip() for s in sys.argv[1].split(',') if s.strip()]
    token = sys.argv[2]
    root = sys.argv[3]
    interval = int(sys.argv[4])
    force = sys.argv[5].lower() == "true"
    
    # 获取过滤参数
    artist_filter = sys.argv[6] if len(sys.argv) > 6 else "*"
    quality_filter = sys.argv[7] if len(sys.argv) > 7 else "*" # 新增第7个参数

    print(f"[DEBUG] 启动: 歌手过滤='{artist_filter}', 音质过滤='{quality_filter}'", flush=True)

    # 首次运行
    for s in sources: 
        sync_repo(s, token, root, force=True, artist_filter=artist_filter, quality_filter=quality_filter)

    # 循环
    while True:
        time.sleep(interval)
        for s in sources: 
            sync_repo(s, token, root, force=force, artist_filter=artist_filter, quality_filter=quality_filter)
