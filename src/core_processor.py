#!/usr/bin/env python3
# Obfuscated: Intelligent Deduplication Stream Processor
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
# 定义音质等级，越靠前品质越高
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
    """
    清洗文件名，用于判断是否为同一首歌。
    去除 [320], [flac], (Live), 后缀名等，只保留 '歌手/专辑/歌名'
    """
    # 去除扩展名
    base, _ = os.path.splitext(filename)
    # 去除方括号内容 [320], [flac] 等
    base = re.sub(r'\[.*?\]', '', base)
    # 去除圆括号内容 (Live), (Cover) 等 (可选，视情况而定，这里偏保守，只去空格)
    # base = re.sub(r'\(.*?\)', '', base) 
    # 去除多余空格
    base = base.strip()
    return base.lower()

def get_quality_score(filename, target_pattern):
    """
    计算文件优先级分数。分数越小，优先级越高。
    0: 完美匹配用户要求
    1: 比用户要求更好
    2: 比用户要求更差
    3: 未知/其他
    """
    fname = filename.lower()
    target = target_pattern.lower().replace("[", "").replace("]", "").strip() # 去除用户输入的括号
    
    # 1. 完美匹配 (包含用户指定的字符)
    if target != "*" and target in fname:
        return 0
    
    # 提取文件中的音质标识
    file_q_index = 999
    target_q_index = 999
    
    # 找到文件当前的音质等级
    for idx, q in enumerate(QUALITY_HIERARCHY):
        if q in fname:
            file_q_index = idx
            break
            
    # 找到用户目标的音质等级
    for idx, q in enumerate(QUALITY_HIERARCHY):
        if q in target:
            target_q_index = idx
            break
            
    # 如果没找到用户的目标等级，默认把所有文件都当做“其他”
    if target_q_index == 999:
        return 3

    # 2. 比较音质
    if file_q_index < target_q_index:
        return 1 # 品质更好 (Index越小品质越高)
    else:
        return 2 # 品质更差

def get_smart_file_list(api, repo_id, artist_filter, quality_filter):
    """
    获取文件列表，并执行去重和优选逻辑
    """
    try:
        log(f"正在获取文件列表并计算最优版本...")
        all_files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
        
        # 1. 歌手/路径初筛
        candidates = []
        artist_rules = [p.strip().lower() for p in artist_filter.split(',') if p.strip()]
        
        for f in all_files:
            if f.endswith(('.gitattributes', 'README.md', '.git', '.json', '.sync_meta')): continue
            
            # 歌手过滤
            if artist_filter != "*":
                f_lower = f.lower()
                # 简单包含逻辑，支持通配符
                if not any((rule.replace("*", "") in f_lower) for rule in artist_rules):
                    continue
            candidates.append(f)

        # 2. 分组去重
        song_groups = defaultdict(list)
        for f in candidates:
            # 使用清洗后的文件名作为 Key (Key相同视为同一首歌)
            key = clean_filename(f)
            song_groups[key].append(f)
            
        # 3. 组内优选
        final_list = []
        for key, group_files in song_groups.items():
            if len(group_files) == 1:
                final_list.append(group_files[0]) # 只有这一个，直接下
            else:
                # 多个版本，开始PK
                # 按分数排序：分数越小越好 (匹配 > 高品质 > 低品质)
                sorted_files = sorted(group_files, key=lambda x: get_quality_score(x, quality_filter))
                winner = sorted_files[0]
                final_list.append(winner)
                # 调试日志：显示选择结果
                # log(f"歌曲 [{key}] 选择了: {os.path.basename(winner)}")

        log(f"智能筛选: 原始 {len(all_files)} -> 歌手匹配 {len(candidates)} -> 最终去重后 {len(final_list)} 首")
        return final_list

    except Exception as e:
        log(f"智能列表计算失败: {e}")
        return []

def download_single_file(repo_id, filename, token, target_root):
    if get_free_space_mb(target_root) < DISK_SAFE_LIMIT_MB: return "DISK_FULL"
    try:
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="dataset",
            token=token,
            local_dir=target_root,
            local_dir_use_symlinks=False, 
            force_download=False
        )
        return "SUCCESS"
    except Exception as e:
        print(f"[ERROR] {filename}: {e}")
        return "ERROR"

def sync_repo(repo_id, token, root_dir, force=False, artist_filter="*", quality_filter="*"):
    safe_name = repo_id.replace("/", "_")
    target_dir = os.path.join(root_dir, safe_name)
    os.makedirs(target_dir, exist_ok=True)
    
    if get_free_space_mb(target_dir) < DISK_SAFE_LIMIT_MB:
        log(f"🛑 磁盘空间不足 {DISK_SAFE_LIMIT_MB}MB，停止下载。")
        return

    api = HfApi(token=token)
    
    # 使用新的智能获取函数
    files_to_download = get_smart_file_list(api, repo_id, artist_filter, quality_filter)
    
    if not files_to_download:
        log("⚠️ 没有符合条件的文件。")
        return

    log(f"准备下载 {len(files_to_download)} 个最优文件...")
    
    success_count = 0
    disk_full = False
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(download_single_file, repo_id, f, token, target_dir): f for f in files_to_download}
        total = len(files_to_download)
        for i, future in enumerate(as_completed(futures)):
            if future.result() == "SUCCESS": success_count += 1
            elif future.result() == "DISK_FULL": 
                disk_full = True
                executor.shutdown(wait=False, cancel_futures=True)
                break
            if i % 20 == 0: print(f"进度: {i}/{total}...", end="\r", flush=True)
                
    print(f"\n") 
    log(f"任务结束。成功: {success_count}/{len(files_to_download)}")
    if disk_full: log("🛑 触发磁盘熔断，已停止。")

if __name__ == "__main__":
    if len(sys.argv) < 4: sys.exit(0)
    sources = [s.strip() for s in sys.argv[1].split(',') if s.strip()]
    token, root = sys.argv[2], sys.argv[3]
    interval = int(sys.argv[4])
    artist_filter = sys.argv[6] if len(sys.argv) > 6 else "*"
    quality_filter = sys.argv[7] if len(sys.argv) > 7 else "*"

    print(f"[DEBUG] 智能模式启动: 优选品质='{quality_filter}'", flush=True)

    for s in sources: 
        sync_repo(s, token, root, force=True, artist_filter=artist_filter, quality_filter=quality_filter)

    log("监控模式已启动...")
    while True:
        time.sleep(interval)
        for s in sources: 
            sync_repo(s, token, root, force=False, artist_filter=artist_filter, quality_filter=quality_filter)
