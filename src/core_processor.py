#!/usr/bin/env python3
# 最终版：智能去重、音质优选、磁盘保护
from huggingface_hub import HfApi, hf_hub_download
import os
import sys
import time
import json
import re
import shutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

# === 配置区域 ===
DISK_SAFE_LIMIT_MB = 1024  # 1GB 保护
# 音质等级：越靠前越优先
QUALITY_HIERARCHY = ['flac24bit', '24bit', 'flac', 'wav', '320', '320k', '192', '128']
# =================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [SYNC] {msg}", flush=True)

def get_free_space_mb(folder):
    try:
        total, used, free = shutil.disk_usage(folder)
        return free // (1024 * 1024)
    except: return 999999

def clean_filename(filename):
    """提取歌曲核心标识（去除音质标签、后缀）"""
    base, _ = os.path.splitext(filename)
    # 去除 [320], [flac] 等
    base = re.sub(r'\[.*?\]', '', base)
    # 去除 (Live) 等 (可选)
    # base = re.sub(r'\(.*?\)', '', base) 
    return base.strip().lower()

def get_quality_score(filename, target_pattern):
    """计算文件优先级 (越小越好)"""
    fname = filename.lower()
    target = target_pattern.lower().replace("[", "").replace("]", "").strip()
    
    # 0级: 完美匹配用户指定字符串
    if target != "*" and target in fname: return 0
    
    # 分析文件音质等级
    file_idx = 999
    for i, q in enumerate(QUALITY_HIERARCHY):
        if q in fname:
            file_idx = i
            break
            
    # 分析目标音质等级
    target_idx = 999
    for i, q in enumerate(QUALITY_HIERARCHY):
        if q in target:
            target_idx = i
            break
            
    if target_idx == 999: return 3 # 无法判断
    
    # 1级: 比目标更好; 2级: 比目标差
    return 1 if file_idx < target_idx else 2

def get_smart_file_list(api, repo_id, artist_filter, quality_filter):
    """获取列表并去重"""
    try:
        log(f"正在分析文件列表并执行智能去重...")
        all_files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
        
        # 1. 歌手筛选
        candidates = []
        artist_rules = [p.strip().lower().replace("*", "") for p in artist_filter.split(',') if p.strip()]
        
        for f in all_files:
            if f.endswith(('.gitattributes', 'README.md', '.git', '.json', '.sync_meta')): continue
            
            if artist_filter != "*":
                f_lower = f.lower()
                if not any(rule in f_lower for rule in artist_rules):
                    continue
            candidates.append(f)

        # 2. 智能去重 (核心逻辑)
        song_groups = defaultdict(list)
        for f in candidates:
            # 只有同一首歌的不同音质版本，key 才会相同
            key = clean_filename(f) 
            song_groups[key].append(f)
            
        # 3. 组内优选
        final_list = []
        for key, group in song_groups.items():
            if len(group) == 1:
                final_list.append(group[0])
            else:
                # 排序：0(完美) < 1(更好) < 2(更差) < 3(未知)
                best = sorted(group, key=lambda x: get_quality_score(x, quality_filter))[0]
                final_list.append(best)

        log(f"筛选统计: 原始 {len(all_files)} -> 歌手匹配 {len(candidates)} -> 智能去重后 {len(final_list)} 首")
        return final_list

    except Exception as e:
        log(f"列表计算失败: {e}")
        return []

def download_file(repo_id, filename, token, root):
    if get_free_space_mb(root) < DISK_SAFE_LIMIT_MB: return "DISK_FULL"
    try:
        hf_hub_download(repo_id=repo_id, filename=filename, repo_type="dataset", token=token, local_dir=root, local_dir_use_symlinks=False, force_download=False)
        return "SUCCESS"
    except Exception as e:
        print(f"[ERROR] {filename}: {e}")
        return "ERROR"

def sync_repo(repo_id, token, root_dir, force=False, artist="*", quality="*"):
    safe_name = repo_id.replace("/", "_")
    target_dir = os.path.join(root_dir, safe_name)
    os.makedirs(target_dir, exist_ok=True)
    
    if get_free_space_mb(target_dir) < DISK_SAFE_LIMIT_MB:
        log(f"🛑 磁盘不足 {DISK_SAFE_LIMIT_MB}MB，任务停止。")
        return

    api = HfApi(token=token)
    files = get_smart_file_list(api, repo_id, artist, quality)
    
    if not files:
        log("没有需要下载的文件。")
        return

    log(f"准备下载 {len(files)} 个最优文件...")
    
    success = 0
    full = False
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(download_file, repo_id, f, token, target_dir): f for f in files}
        total = len(files)
        for i, fut in enumerate(as_completed(futures)):
            if fut.result() == "SUCCESS": success += 1
            elif fut.result() == "DISK_FULL": 
                full = True
                ex.shutdown(wait=False, cancel_futures=True)
                break
            if i % 50 == 0: print(f"进度: {i}/{total}...", end="\r", flush=True)
    
    print(f"\n")
    log(f"完成。成功: {success}/{len(files)}")
    if full: log("🛑 磁盘已满，已熔断停止。")

if __name__ == "__main__":
    if len(sys.argv) < 4: sys.exit(0)
    sources = [s.strip() for s in sys.argv[1].split(',') if s.strip()]
    token, root, interval = sys.argv[2], sys.argv[3], int(sys.argv[4])
    artist = sys.argv[6] if len(sys.argv) > 6 else "*"
    quality = sys.argv[7] if len(sys.argv) > 7 else "*"

    print(f"[DEBUG] 智能模式: 歌手='{artist}', 优选音质='{quality}'", flush=True)

    for s in sources: sync_repo(s, token, root, force=True, artist=artist, quality=quality)

    log("守护进程待机中 (每小时检查)...")
    while True:
        time.sleep(interval)
        # 为防爆盘，守护模式建议不进行全量扫描，只保持活跃，或者你可以取消注释下面这行
        # for s in sources: sync_repo(s, token, root, force=False, artist=artist, quality=quality)
