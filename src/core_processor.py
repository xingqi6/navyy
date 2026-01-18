#!/usr/bin/env python3
# Obfuscated: Core Processor
from huggingface_hub import snapshot_download, HfApi
import os
import sys
import time
import json
from datetime import datetime

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [SYNC] {msg}")

def sync_repo(repo_id, token, root_dir, force=False):
    # 将 user/repo 转换为目录名 user_repo
    safe_name = repo_id.replace("/", "_")
    target_dir = os.path.join(root_dir, safe_name)
    os.makedirs(target_dir, exist_ok=True)
    
    # 简单的元数据检查
    meta_path = os.path.join(target_dir, ".sync_meta")
    try:
        api = HfApi(token=token)
        remote = api.repo_info(repo_id=repo_id, repo_type="dataset")
        remote_sha = remote.sha
    except:
        log(f"Failed to fetch info for {repo_id}")
        return

    local_sha = ""
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                local_sha = json.load(f).get("sha", "")
        except: pass

    if not force and local_sha == remote_sha:
        log(f"No changes for {repo_id}")
        return

    log(f"Downloading {repo_id}...")
    try:
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            local_dir=target_dir,
            token=token,
            ignore_patterns=[".git*", "README*"]
        )
        with open(meta_path, "w") as f:
            json.dump({"sha": remote_sha}, f)
        log(f"Synced {repo_id}")
    except Exception as e:
        log(f"Error syncing {repo_id}: {e}")

if __name__ == "__main__":
    # args: sources_str, token, music_dir, interval, force_str
    if len(sys.argv) < 5: sys.exit(0)
    
    sources = [s.strip() for s in sys.argv[1].split(',') if s.strip()]
    token = sys.argv[2]
    root = sys.argv[3]
    interval = int(sys.argv[4])
    force = sys.argv[5].lower() == "true" if len(sys.argv) > 5 else False

    # 首次运行
    for s in sources: sync_repo(s, token, root, force=True)

    # 循环
    while True:
        time.sleep(interval)
        for s in sources: sync_repo(s, token, root, force=force)
