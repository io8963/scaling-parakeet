# autobuild.py - Fixed Build Time Microsecond Precision

import os
import shutil
import glob
import hashlib
from typing import List, Dict, Any
from collections import defaultdict
from datetime import datetime, timezone, timedelta 
import subprocess # 用于执行 Git 命令
import shlex      # 用于安全处理命令字符串
import json
from typing import Dict, Any

import config
from parser import get_metadata_and_content
import generator

# [新增] 定义清单文件路径
MANIFEST_FILE = os.path.join(os.path.dirname(__file__), '.build_manifest.json')

# [新增] 定义 UTC+8 时区信息
TIMEZONE_OFFSET = timedelta(hours=8)
TIMEZONE_INFO = timezone(TIMEZONE_OFFSET)

# --- Manifest 和其他辅助函数 (保持不变) ---
def load_manifest() -> Dict[str, Any]:
    """加载上一次的构建清单文件。"""
    try:
        with open(MANIFEST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_manifest(manifest: Dict[str, Any]):
    """保存当前的构建清单文件。"""
    try:
        with open(MANIFEST_FILE, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f"警告：无法写入构建清单文件 {MANIFEST_FILE}: {e}")

def get_full_content_hash(filepath: str) -> str:
    """计算文件的完整 SHA256 哈希值。用于 Manifest。"""
    h = hashlib.sha256()
    try:
        with open(filepath, 'rb') as file:
            while True:
                chunk = file.read(4096)
                if not chunk:
                    break
                h.update(chunk)
    except IOError:
        return ""
    return h.hexdigest()

def hash_file(filepath: str) -> str:
    """计算文件的 SHA256 哈希值前 8 位。用于 CSS 文件名。"""
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            hasher.update(f.read())
        return hasher.hexdigest()[:8]
    except FileNotFoundError:
        return 'nohash'

# [最终修复 FUNCTION] 获取文件的最后修改时间 (引入微秒精度)
def format_file_mod_time(filepath: str) -> str:
    """
    获取文件的最后修改时间。
    优先级：1. Git Author Time -> 2. 文件系统修改时间 -> 3. 当前构建时间。
    并确保输出包含微秒以保证唯一性。
    """
    
    # 辅助函数：将 datetime 转换为中文格式的 UTC+8 字符串
    def format_dt(dt: datetime, source: str) -> str:
        # 确保 datetime 对象带有正确的时区信息
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            # 如果没有时区信息，假设它是 UTC (如 os.path.getmtime)，并调整时区
            # 注意：datetime.fromtimestamp 在某些系统上返回本地时间，我们在这里将其视为无时区，让 astimezone 统一处理
            dt = dt.astimezone(TIMEZONE_INFO) 
        else:
            # 否则直接转换为 UTC+8
            dt = dt.astimezone(TIMEZONE_INFO)
            
        # [核心修复] 使用微秒 (%f) 格式化时间
        time_str = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
        
        # 移除末尾的零和点，使输出更简洁，但保留非零微秒
        time_str = time_str.rstrip('0').rstrip('.')
        
        return f"本文构建时间: {time_str} (UTC+8 - {source})"
    
    # --- 1. 尝试获取 Git 最后提交时间 (Author Time) ---
    try:
        git_command = ['git', 'log', '-1', '--pretty=format:%aI', '--', filepath]
        result = subprocess.run(git_command, capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            git_time_str = result.stdout.strip()
            if git_time_str:
                try:
                    mtime_dt_tz = datetime.fromisoformat(git_time_str)
                except ValueError:
                    if git_time_str.endswith('Z'):
                        git_time_str = git_time_str.replace('Z', '+00:00')
                    mtime_dt_tz = datetime.fromisoformat(git_time_str)
                
                return format_dt(mtime_dt_tz, 'Git')

    except Exception as e:
        pass
    
    # --- 2. 尝试获取文件系统修改时间 (次级回退) ---
    try:
        timestamp = os.path.getmtime(filepath)
        fs_mtime = datetime.fromtimestamp(timestamp)
        return format_dt(fs_mtime, 'Filesystem')
        
    except FileNotFoundError:
        pass

    except Exception as e:
        pass
        
    # --- 3. 最终回退：使用当前构建时间 ---
    now_utc = datetime.now(timezone.utc)
    return format_dt(now_utc, 'Fallback')


def build_site():
    print("\n" + "="*40)
    print("   🚀 STARTING BUILD PROCESS (Incremental Build Enabled)")
    print("="*40 + "\n")
    
    # -------------------------------------------------------------------------
    # [1/5] 准备工作 & 增量构建初始化
    # -------------------------------------------------------------------------
    print("[1/5] Preparing build directory and loading manifest...")
    
    os.makedirs(config.BUILD_DIR, exist_ok=True) 
    os.makedirs(config.POSTS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.TAGS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.STATIC_OUTPUT_DIR, exist_ok=True)

    old_manifest = load_manifest()
    new_manifest = {}
    
    posts_to_build: List[Dict[str, Any]] = [] 
    posts_data_changed = False      
    
    # -------------------------------------------------------------------------
    # [2/5] 资源处理 (保持不变)
    # -------------------------------------------------------------------------
    print("\n[2/5] Processing Assets...")
    assets_dir = os.path.join(config.BUILD_DIR, 'assets')
    os.makedirs(assets_dir, exist_ok=True)
    
    if os.path.exists(config.STATIC_DIR):
        shutil.copytree(config.STATIC_DIR, config.STATIC_OUTPUT_DIR, dirs_exist_ok=True)
    
    css_source = 'assets/style.css'
    if os.path.exists(css_source):
        css_hash = hash_file(css_source)
        new_css = f"style.{css_hash}.css"
        config.CSS_FILENAME = new_css
        shutil.copy2(css_source, os.path.join(assets_dir, new_css))
    else:
        config.CSS_FILENAME = 'style.css'

    # -------------------------------------------------------------------------
    # [3/5] 解析 Markdown (保持不变，但使用了新的 format_file_mod_time)
    # -------------------------------------------------------------------------
    print("\n[3/5] Parsing Markdown Files...")
    
    md_files = glob.glob(os.path.join(config.MARKDOWN_DIR, '*.md'))
    if not md_files: md_files = glob.glob('*.md')
    
    parsed_posts = []
    tag_map = defaultdict(list)
    source_md_paths: Set[str] = set()

    for md_file in md_files:
        relative_path = os.path.relpath(md_file, os.path.dirname(__file__)).replace('\\', '/')
        source_md_paths.add(relative_path)
        
        current_hash = get_full_content_hash(md_file)
        old_item = old_manifest.get(relative_path, {})
        old_hash = old_item.get('hash')
        old_link = old_item.get('link')

        needs_full_build = (current_hash != old_hash) or (old_link is None)
        
        if needs_full_build:
            print(f"   -> [CHANGED/NEW] {os.path.basename(md_file)}")
            posts_data_changed = True
        else:
            print(f"   -> [SKIPPED HTML] {os.path.basename(md_file)}")

        metadata, content_md, content_html, toc_html = get_metadata_and_content(md_file)
        
        # 使用修正后的函数获取时间
        mod_time_cn = format_file_mod_time(md_file)

        # 自动补全 slug
        if 'slug' not in metadata:
            filename_slug = os.path.splitext(os.path.basename(md_file))[0]
            metadata['slug'] = filename_slug

        slug = str(metadata['slug']).lower()
        file_name = os.path.basename(md_file)
        
        # 404/Hidden Pages Logic (特殊页面处理)
        if slug == '404' or file_name == '404.md':
            special_post = { 
                **metadata, 'content_html': content_html, 'toc_html': '', 
                'link': '404.html', 'footer_time_info': mod_time_cn
            }
            if needs_full_build:
                 generator.generate_post_page(special_post)
            new_manifest[relative_path] = {'hash': current_hash, 'link': '404.html'}
            continue 

        if metadata.get('hidden') is True: 
            if slug == 'about' or file_name == config.ABOUT_PAGE:
                 special_post = { 
                     **metadata, 'content_html': content_html, 'toc_html': '', 
                     'link': 'about.html', 'footer_time_info': mod_time_cn
                 }
                 if needs_full_build:
                     generator.generate_page_html(
                         special_post['content_html'], special_post['title'], 
                         'about', 'about.html', special_post['footer_time_info']
                     )
            
            new_manifest[relative_path] = {'hash': current_hash, 'link': 'hidden'}
            continue 

        # 检查普通文章的必要字段
        if not all(k in metadata for k in ['date', 'title']): 
            continue
            
        # 普通文章处理
        post_link = os.path.join(config.POSTS_DIR_NAME, f"{slug}.html").replace('\\', '/')
        post = {
            **metadata, 
            'content_markdown': content_md,
            'content_html': content_html,
            'toc_html': toc_html,
            'link': post_link,
            'footer_time_info': mod_time_cn 
        }
        
        # 检查 Slug 是否变化
        if old_link and old_link != post_link and not needs_full_build:
            posts_data_changed = True
            print(f"   -> [SLUG CHANGED] {os.path.basename(md_file)}. Rebuilding all list pages.")
            
        # 收集标签
        for tag_data in post.get('tags', []):
            tag_map[tag_data['name']].append(post)
            
        parsed_posts.append(post)
        
        # 更新 Manifest 和 posts_to_build 列表
        new_manifest[relative_path] = {'hash': current_hash, 'link': post_link}
        
        if needs_full_build or (old_link and old_link != post_link):
            posts_to_build.append(post) 
            
        # 如果 Slug 变化，删除旧的 HTML 文件
        if old_link and old_link != post_link and old_link != 'hidden' and old_link != '404.html':
             old_html_path = os.path.join(config.BUILD_DIR, old_link.strip('/'))
             if os.path.exists(old_html_path):
                os.remove(old_html_path)
                print(f"   -> [CLEANUP] Deleted old HTML file: {old_html_path}")

    # 清理被删除的源文件
    deleted_paths = set(old_manifest.keys()) - source_md_paths
    for deleted_path in deleted_paths:
        item = old_manifest[deleted_path]
        deleted_link = item.get('link')
        print(f"   -> [DELETED] Source file {deleted_path} removed.")
        posts_data_changed = True 
        
        if deleted_link and deleted_link != 'hidden' and deleted_link != '404.html':
            deleted_html_path = os.path.join(config.BUILD_DIR, deleted_link.strip('/'))
            if os.path.exists(deleted_html_path):
                os.remove(deleted_html_path)
                print(f"   -> [CLEANUP] Deleted post HTML file: {deleted_html_path}")
                
    final_parsed_posts = sorted(parsed_posts, key=lambda p: p['date'], reverse=True)
    
    print(f"   -> Successfully parsed {len(final_parsed_posts)} blog posts. ({len(posts_to_build)} HTML files rebuilt)")

    # -------------------------------------------------------------------------
    # [4/5] P/N Navigation Injection & Build Time
    # -------------------------------------------------------------------------
    for i, post in enumerate(final_parsed_posts):
        prev_post_data = final_parsed_posts[i - 1] if i > 0 else None
        next_post_data = final_parsed_posts[i + 1] if i < len(final_parsed_posts) - 1 else None

        post['prev_post_nav'] = None
        if prev_post_data:
            post['prev_post_nav'] = {
                'title': prev_post_data['title'],
                'link': prev_post_data['link']
            }

        post['next_post_nav'] = None
        if next_post_data:
            post['next_post_nav'] = {
                'title': next_post_data['title'],
                'link': next_post_data['link']
            }

    # 为列表/静态页面生成一个通用的网站构建时间 (UTC+8) (基于当前时间)
    now_utc = datetime.now(timezone.utc)
    now_utc8 = now_utc.astimezone(TIMEZONE_INFO)
    # [列表页使用不带微秒的简洁格式]
    global_build_time_cn = f"网站构建时间: {now_utc8.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)"
    
    # -------------------------------------------------------------------------
    # [5/5] 生成 HTML
    # -------------------------------------------------------------------------
    print("\n[5/5] Generating HTML...")
    
    # 1. 生成普通文章详情页 (使用 post 中独特的 footer_time_info)
    for post in posts_to_build:
        generator.generate_post_page(post) 

    # 2. 生成列表页 (使用 global_build_time_cn)
    if not old_manifest or posts_data_changed:
        print("   -> [REBUILDING] Index, Archive, Tags, RSS (Post data changed)")
        
        generator.generate_index_html(final_parsed_posts, global_build_time_cn) 
        generator.generate_archive_html(final_parsed_posts, global_build_time_cn) 
        generator.generate_tags_list_html(tag_map, global_build_time_cn) 

        for tag, posts in tag_map.items():
            sorted_tag = sorted(posts, key=lambda p: p['date'], reverse=True)
            generator.generate_tag_page(tag, sorted_tag, global_build_time_cn) 

        generator.generate_robots_txt()
        
        with open(os.path.join(config.BUILD_DIR, config.SITEMAP_FILE), 'w', encoding='utf-8') as f:
            f.write(generator.generate_sitemap(final_parsed_posts))
        with open(os.path.join(config.BUILD_DIR, config.RSS_FILE), 'w', encoding='utf-8') as f:
            f.write(generator.generate_rss(final_parsed_posts))
            
    else:
        print("   -> [SKIPPED] Index, Archive, Tags, RSS (No post data change)")

    # 3. 保存新的构建清单
# autobuild.py (已修复最后一行语法错误)
# ... (文件的所有其他内容保持不变)

    # 3. 保存新的构建清单
    save_manifest(new_manifest)
    print("   -> Manifest file updated.")
    
    print("\n✅ BUILD COMPLETE")

if __name__ == '__main__': # <-- 关键修复：添加了冒号 (:) 和第二个下划线 (__)
    build_site()
