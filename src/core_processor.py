#!/usr/bin/env python3
# Obfuscated: Data Stream Processor
from huggingface_hub import snapshot_download, HfApi
import os
import sys
import time
import json
from datetime import datetime

def sys_log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [KERNEL_IO] {msg}")

def get_remote_meta(repo_id, token):
    try:
        api = HfApi(token=token)
        info = api.repo_info(repo_id=repo_id, repo_type="dataset")
        return {"sha": info.sha, "last_modified": str(info.last_modified)}
    except Exception as e:
        sys_log(f"Connection warning for node {repo_id}: {str(e)}")
        return None

def sync_shard(dataset_name, token, base_dir, force=False):
    # 将 repo/name 转换为 repo_name 以便作为目录名
    safe_folder = dataset_name.replace("/", "_")
    target_path = os.path.join(base_dir, safe_folder)
    os.makedirs(target_path, exist_ok=True)
    
    meta_file = os.path.join(target_path, ".shard_meta")
    
    remote_meta = get_remote_meta(dataset_name, token)
    if not remote_meta:
        return

    local_meta = {}
    if os.path.exists(meta_file):
        try:
            with open(meta_file, "r") as f:
                local_meta = json.load(f)
        except:
            pass

    if not force and local_meta.get("sha") == remote_meta.get("sha"):
        sys_log(f"Shard {safe_folder} is consistent.")
        return

    sys_log(f"Resyncing shard: {dataset_name} -> {target_path}")
    try:
        snapshot_download(
            repo_id=dataset_name,
            repo_type="dataset",
            local_dir=target_path,
            token=token,
            # 排除 git 目录和非媒体文件以加快速度
            ignore_patterns=[".git*", "*.md", "README*"]
        )
        with open(meta_file, "w") as f:
            json.dump(remote_meta, f)
        sys_log(f"Shard {safe_folder} synced successfully.")
    except Exception as e:
        sys_log(f"Sync error on {dataset_name}: {str(e)}")

if __name__ == "__main__":
    # 参数: sources_list token base_dir interval force
    if len(sys.argv) < 4:
        sys.exit(0)

    sources_str = sys.argv[1]
    token = sys.argv[2]
    base_dir = sys.argv[3]
    interval = int(sys.argv[4]) if len(sys.argv) > 4 else 3600
    force_mode = sys.argv[5].lower() == "true" if len(sys.argv) > 5 else False

    # 解析多个数据集，以逗号分隔
    # 例如: "user1/music,user2/pop,user3/classical"
    datasets = [d.strip() for d in sources_str.split(',') if d.strip()]

    sys_log(f"Initializing stream processor. Monitoring {len(datasets)} sources.")

    # 首次立即执行
    for ds in datasets:
        sync_shard(ds, token, base_dir, force=True)

    # 循环监听
    while True:
        time.sleep(interval)
        for ds in datasets:
            sync_shard(ds, token, base_dir, force=force_mode)
