#!/usr/bin/env python3
# Obfuscated: State Manager
from huggingface_hub import HfApi
import sys, os, tempfile, tarfile
from datetime import datetime

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [BACKUP] {msg}")

def upload(token, repo, data_dir):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"backup_{timestamp}.tar.gz"
        tmp = os.path.join(tempfile.gettempdir(), fname)
        
        with tarfile.open(tmp, "w:gz") as tar:
            for f in os.listdir(data_dir):
                if "cache" not in f.lower(): # 排除缓存
                    tar.add(os.path.join(data_dir, f), arcname=f)
        
        api = HfApi(token=token)
        api.upload_file(path_or_fileobj=tmp, path_in_repo=fname, repo_id=repo, repo_type="dataset")
        log(f"Uploaded {fname}")
        
        # 简单清理旧备份(保留最近5个)
        files = api.list_repo_files(repo_id=repo, repo_type="dataset")
        backups = sorted([f for f in files if f.startswith("backup_")])
        if len(backups) > 5:
            for old in backups[:-5]:
                api.delete_file(old, repo, repo_type="dataset")
                
        os.remove(tmp)
    except Exception as e:
        log(f"Upload failed: {e}")

def download(token, repo, data_dir):
    try:
        os.makedirs(data_dir, exist_ok=True)
        api = HfApi(token=token)
        files = api.list_repo_files(repo_id=repo, repo_type="dataset")
        backups = sorted([f for f in files if f.startswith("backup_")])
        if not backups: return

        latest = backups[-1]
        log(f"Restoring {latest}...")
        with tempfile.TemporaryDirectory() as td:
            path = api.hf_hub_download(repo, latest, repo_type="dataset", local_dir=td)
            with tarfile.open(path, "r:gz") as tar:
                tar.extractall(data_dir)
        log("Restore complete")
    except Exception as e:
        log(f"Restore failed: {e}")

if __name__ == "__main__":
    action = sys.argv[1] # upload/download
    token = sys.argv[2]
    repo = sys.argv[3]
    path = sys.argv[4]
    
    if action == "upload": upload(token, repo, path)
    elif action == "download": download(token, repo, path)
