#!/usr/bin/env python3
# Obfuscated Name: Data Synchronization Core
from huggingface_hub import snapshot_download, HfApi
import os
import sys
import time
import json
from datetime import datetime

# 伪装日志输出
def log(msg):
    print(f"[{datetime.now()}] [KERNEL] {msg}")

def get_dataset_info(repo_id, token):
    try:
        api = HfApi(token=token)
        info = api.repo_info(repo_id=repo_id, repo_type="dataset")
        return {"sha": info.sha, "last_modified": str(info.last_modified)}
    except Exception as e:
        log(f"Fetch info failed for {repo_id}: {str(e)}")
        return None

def sync_dataset(dataset_name, token, base_music_dir, force=False):
    # 为每个数据集创建一个子目录，例如 /music/user_repo_name
    safe_name = dataset_name.replace("/", "_")
    target_dir = os.path.join(base_music_dir, safe_name)
    os.makedirs(target_dir, exist_ok=True)
    
    info_file = os.path.join(target_dir, ".meta_info")
    
    remote_info = get_dataset_info(dataset_name, token)
    if not remote_info:
        return

    local_info = {}
    if os.path.exists(info_file):
        try:
            with open(info_file, "r") as f:
                local_info = json.load(f)
        except:
            pass

    if not force and local_info.get("sha") == remote_info.get("sha"):
        log(f"Resource {safe_name} is up to date.")
        return

    log(f"Syncing resource: {dataset_name} -> {target_dir}")
    try:
        snapshot_download(
            repo_id=dataset_name,
            repo_type="dataset",
            local_dir=target_dir,
            token=token,
            ignore_patterns=["*.git*"] # 排除git文件
        )
        with open(info_file, "w") as f:
            json.dump(remote_info, f)
        log(f"Sync complete: {safe_name}")
    except Exception as e:
        log(f"Sync error {dataset_name}: {str(e)}")

if __name__ == "__main__":
    # 接收逗号分隔的数据集列表
    datasets_str = sys.argv[1]
    token = sys.argv[2]
    music_dir = sys.argv[3]
    interval = int(sys.argv[4]) if len(sys.argv) > 4 else 3600
    force = sys.argv[5].lower() == "true" if len(sys.argv) > 5 else False

    # 解析多个数据集
    dataset_list = [d.strip() for d in datasets_str.split(',') if d.strip()]

    # 首次运行全部同步
    for ds in dataset_list:
        sync_dataset(ds, token, music_dir, force=True)

    # 循环检查
    while True:
        time.sleep(interval)
        for ds in dataset_list:
            sync_dataset(ds, token, music_dir, force=force)
