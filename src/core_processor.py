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

def sync_repo(repo_id, token, root_dir, force=False, patterns=None):
    # 将 patterns 字符串转换为列表，例如 "周杰伦*,陈奕迅*" -> ["周杰伦*", "陈奕迅*"]
    if patterns and patterns != "*":
        allow_patterns = [p.strip() for p in patterns.split(',') if p.strip()]
    else:
        allow_patterns = None # 下载所有

    safe_name = repo_id.replace("/", "_")
    target_dir = os.path.join(root_dir, safe_name)
    os.makedirs(target_dir, exist_ok=True)
    
    # 元数据检查
    meta_path = os.path.join(target_dir, ".sync_meta")
    remote_sha = ""
    try:
        api = HfApi(token=token)
        # 获取数据集信息
        remote = api.repo_info(repo_id=repo_id, repo_type="dataset")
        remote_sha = remote.sha
    except Exception as e:
        log(f"Fetch info failed: {e}")
        # 如果获取失败，但我们有过滤规则，还是尝试下载吧，防止因为API波动漏下
    
    local_sha = ""
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                local_sha = json.load(f).get("sha", "")
        except: pass

    # 如果 SHA 没变且不是强制更新，则跳过
    # 注意：如果加了过滤规则，建议手动 Force 或者忽略这个检查，
    # 但为了节省流量，这里还是保留检查。如果想换过滤规则，建议在HF Factory Reboot。
    if not force and local_sha == remote_sha and remote_sha != "":
        log(f"No changes for {repo_id}")
        return

    log(f"Downloading {repo_id} (Filter: {allow_patterns})...")
    try:
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            local_dir=target_dir,
            token=token,
            ignore_patterns=[".git*", "README*"], # 永远排除这些
            allow_patterns=allow_patterns # 核心修改：只下载允许的
        )
        # 只有在没有过滤或者下载成功时才保存 SHA
        # 如果是部分下载，保存 SHA 也行，下次有变动会再触发 snapshot_download
        if remote_sha:
            with open(meta_path, "w") as f:
                json.dump({"sha": remote_sha}, f)
        log(f"Synced {repo_id}")
    except Exception as e:
        log(f"Error syncing {repo_id}: {e}")

if __name__ == "__main__":
    # args: sources_str, token, music_dir, interval, force_str, filter_str
    if len(sys.argv) < 5: sys.exit(0)
    
    sources = [s.strip() for s in sys.argv[1].split(',') if s.strip()]
    token = sys.argv[2]
    root = sys.argv[3]
    interval = int(sys.argv[4])
    force = sys.argv[5].lower() == "true" if len(sys.argv) > 5 else False
    
    # 获取第6个参数作为过滤规则
    filter_pattern = sys.argv[6] if len(sys.argv) > 6 else "*"

    # 首次运行
    for s in sources: sync_repo(s, token, root, force=True, patterns=filter_pattern)

    # 循环
    while True:
        time.sleep(interval)
        for s in sources: sync_repo(s, token, root, force=force, patterns=filter_pattern)
