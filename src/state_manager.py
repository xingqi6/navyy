#!/usr/bin/env python3
# Obfuscated: State Persistence Manager
from huggingface_hub import HfApi
import sys
import os
import time
from datetime import datetime
import tempfile
import tarfile

def sys_log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [STATE_MGR] {msg}")

def cleanup_old_snapshots(api, repo_id, retention=5):
    try:
        files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
        snapshots = [f for f in files if f.startswith('sys_snapshot_') and f.endswith('.tar.gz')]
        snapshots.sort()
        
        if len(snapshots) >= retention:
            to_remove = snapshots[:(len(snapshots) - retention + 1)]
            for item in to_remove:
                api.delete_file(path_in_repo=item, repo_id=repo_id, repo_type="dataset")
                sys_log(f"Pruned old snapshot: {item}")
    except Exception as e:
        sys_log(f"Retention policy error: {str(e)}")

def push_state(data_dir, token, repo_id):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sys_snapshot_{timestamp}.tar.gz"
    tmp_path = os.path.join(tempfile.gettempdir(), filename)
    
    try:
        with tarfile.open(tmp_path, "w:gz") as tar:
            for item in os.listdir(data_dir):
                full_path = os.path.join(data_dir, item)
                # 排除大文件缓存，只备份数据库和配置
                if "cache" in item.lower():
                    continue
                tar.add(full_path, arcname=item)
        
        api = HfApi(token=token)
        api.upload_file(
            path_or_fileobj=tmp_path,
            path_in_repo=filename,
            repo_id=repo_id,
            repo_type="dataset"
        )
        sys_log(f"State captured: {filename}")
        cleanup_old_snapshots(api, repo_id)
        
    except Exception as e:
        sys_log(f"State capture failed: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def pull_state(data_dir, token, repo_id):
    try:
        os.makedirs(data_dir, exist_ok=True)
        api = HfApi(token=token)
        files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
        snapshots = [f for f in files if f.startswith('sys_snapshot_') and f.endswith('.tar.gz')]
        
        if not snapshots:
            sys_log("No existing state found. Initializing fresh.")
            return

        latest = sorted(snapshots)[-1]
        sys_log(f"Restoring state from: {latest}")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = api.hf_hub_download(
                repo_id=repo_id,
                filename=latest,
                repo_type="dataset",
                local_dir=temp_dir
            )
            with tarfile.open(local_path, "r:gz") as tar:
                tar.extractall(path=data_dir)
        sys_log("State restoration complete.")
    except Exception as e:
        sys_log(f"State restore failed: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        sys.exit(1)

    mode = sys.argv[1] # upload / download
    token = sys.argv[2]
    repo_id = sys.argv[3]
    data_dir = sys.argv[4]

    if mode == "upload":
        push_state(data_dir, token, repo_id)
    elif mode == "download":
        pull_state(data_dir, token, repo_id)
