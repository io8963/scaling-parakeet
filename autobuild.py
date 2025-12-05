# autobuild.py - Incremental Build Enabled

import os
import shutil
import glob
import hashlib
from typing import List, Dict, Any, Set
from collections import defaultdict
from datetime import datetime, timezone, timedelta 
import subprocess # 用于执行 Git 命令
import shlex      # 用于安全处理命令字符串
# [新增]
import json
from typing import Dict, Any

import config
from parser import get_metadata_and_content
import generator

# [新增] 定义清单文件路径
MANIFEST_FILE = os.path.join(os.path.dirname(__file__), '.build_manifest.json')

# [新增] Manifest 辅助函数
def load_manifest() -> Dict[str, Any]:
    """加载上一次的构建清单文件。"""
    try:
        with open(MANIFEST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # 如果文件不存在或格式错误，返回空清单
        return {}

def save_manifest(manifest: Dict[str, Any]):
    """保存当前的构建清单文件。"""
    try:
        with open(MANIFEST_FILE, 'w', encoding='utf-8') as f:
            # 使用 indent=4 提高可读性
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

# [新增] 定义 UTC+8 时区信息
TIMEZONE_OFFSET = timedelta(hours=8)
TIMEZONE_INFO = timezone(TIMEZONE_OFFSET)

# --- 检查依赖 ---
try:
    import pygments
except ImportError:
    pass

def hash_file(filepath: str) -> str:
    """计算文件的 SHA256 哈希值前 8 位。用于 CSS 文件名。"""
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            hasher.update(f.read())
        return hasher.hexdigest()[:8]
    except FileNotFoundError:
        return 'nohash'

# [最终修复 FUNCTION] 获取文件的最后修改时间 (强制使用 Git Author Time) 并格式化为 UTC+8
def format_file_mod_time(filepath: str) -> str:
    """获取文件的最后修改时间 (强制使用 Git Author Time) 并格式化为中文构建时间 (UTC+8)。"""
    
    # 尝试获取 Git 最后提交时间 (使用 Author Date %aI，通常更接近实际修改日期)
    try:
        # 使用 subprocess.run 代替 os.popen，提供更精细的错误控制
        git_command = ['git', 'log', '-1', '--pretty=format:%aI', '--', filepath]
        
        # check=False: 不在命令失败时抛异常，我们手动检查 returncode
        result = subprocess.run(git_command, capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode != 0:
             # 如果 Git 命令执行失败 (如：文件不存在, 不在 Git 仓库, 或文件未追踪)
             # 打印错误信息辅助排查
             print(f"   [WARNING] Git failed for {filepath}: {result.stderr.strip()}")
             raise Exception("Git command failed or file is untracked.")

        git_time_str = result.stdout.strip()
        
        if git_time_str:
            # 解析 ISO 时间字符串，datetime.fromisoformat 会正确处理时区偏移
            try:
                mtime_dt_tz = datetime.fromisoformat(git_time_str)
            except ValueError:
                # 再次尝试处理常见的时区格式问题
                if git_time_str.endswith('Z'):
                    git_time_str = git_time_str.replace('Z', '+00:00')
                mtime_dt_tz = datetime.fromisoformat(git_time_str)
            
            # 转换为 UTC+8 (保证显示时区一致性)
            mtime_dt_utc8 = mtime_dt_tz.astimezone(TIMEZONE_INFO)
            
            return f"本文构建时间: {mtime_dt_utc8.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8 - Git)"

        # Git 成功运行但文件未被追踪/无历史记录，进入回退
        raise Exception("Git time not found (no history).") 

    except Exception as e:
        # 所有 Git 相关错误的回退逻辑
        # 强制使用当前的构建时间作为文章的 fallback 时间。
        now_utc = datetime.now(timezone.utc)
        now_utc8 = now_utc.astimezone(TIMEZONE_INFO)
        # 标记为 Fallback，表示未能获取到历史修改时间，该时间是当前构建时间
        return f"本文构建时间: {now_utc8.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8 - Fallback)"


def build_site():
    print("\n" + "="*40)
    print("   🚀 STARTING BUILD PROCESS (Incremental Build Enabled)")
    print("="*40 + "\n")
    
    # -------------------------------------------------------------
    # 1. 准备工作 & 增量构建初始化
    # -------------------------------------------------------------
    print("[1/4] Preparing build directory and loading manifest...")
    
    # [MODIFIED] 移除 shutil.rmtree(config.BUILD_DIR)，改为增量处理
    # 确保所有目录存在 (exist_ok=True 实现增量)
    os.makedirs(config.BUILD_DIR, exist_ok=True) 
    os.makedirs(config.POSTS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.TAGS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.STATIC_OUTPUT_DIR, exist_ok=True)

    # 加载上次的构建清单
    old_manifest = load_manifest()
    new_manifest = {}
    
    # 存储需要重新生成 HTML 的文章对象
    posts_to_build: List[Dict[str, Any]] = [] 
    # 标志位：文章集合信息是否变化 (影响列表页、RSS、Sitemap)
    posts_data_changed = False      
    
    # -------------------------------------------------------------
    # 2. 资源处理
    # -------------------------------------------------------------
    print("\n[2/4] Processing Assets...")
    assets_dir = os.path.join(config.BUILD_DIR, 'assets')
    os.makedirs(assets_dir, exist_ok=True)
    
    # 复制静态文件
    if os.path.exists(config.STATIC_DIR):
        shutil.copytree(config.STATIC_DIR, config.STATIC_OUTPUT_DIR, dirs_exist_ok=True)
    
    # CSS 哈希和复制 (保持不变)
    css_source = 'assets/style.css'
    if os.path.exists(css_source):
        css_hash = hash_file(css_source)
        new_css = f"style.{css_hash}.css"
        config.CSS_FILENAME = new_css
        shutil.copy2(css_source, os.path.join(assets_dir, new_css))
    else:
        config.CSS_FILENAME = 'style.css'

    # -------------------------------------------------------------
    # 3. 解析 Markdown (应用增量逻辑)
    # -------------------------------------------------------------
    print("\n[3/4] Parsing Markdown Files...")
    
    # 兼容处理：确保能找到 Markdown 文件
    md_files = glob.glob(os.path.join(config.MARKDOWN_DIR, '*.md'))
    if not md_files: md_files = glob.glob('*.md')
    
    parsed_posts = []
    tag_map = defaultdict(list)
    
    # [新增] 追踪当前找到的所有 Markdown 文件的相对路径
    source_md_paths: Set[str] = set()

    for md_file in md_files:
        # 使用相对于项目根目录的路径作为 Manifest Key
        relative_path = os.path.relpath(md_file, os.path.dirname(__file__)).replace('\\', '/')
        source_md_paths.add(relative_path)
        
        # 1. 计算当前哈希
        current_hash = get_full_content_hash(md_file)
        
        # 2. 从旧清单中查找状态
        old_item = old_manifest.get(relative_path, {})
        old_hash = old_item.get('hash')
        old_link = old_item.get('link')

        # 3. 判断是否需要重新生成 HTML (内容哈希变动, 或清单中没有上次的链接)
        needs_full_build = (current_hash != old_hash) or (old_link is None)
        
        if needs_full_build:
            print(f"   -> [CHANGED/NEW] {os.path.basename(md_file)}")
            posts_data_changed = True
        else:
            print(f"   -> [SKIPPED HTML] {os.path.basename(md_file)}")

        # 4. 解析内容 (无论是否变动，都需要解析元数据来构建列表页)
        metadata, content_md, content_html, toc_html = get_metadata_and_content(md_file)
        
        # 自动补全 slug
        if 'slug' not in metadata:
            filename_slug = os.path.splitext(os.path.basename(md_file))[0]
            metadata['slug'] = filename_slug

        slug = str(metadata['slug']).lower()
        file_name = os.path.basename(md_file)
        
        mod_time_cn = format_file_mod_time(md_file)
        
        # -------------------------------------------------------
        # 404/Hidden Pages Logic (特殊页面处理)
        # -------------------------------------------------------
        if slug == '404' or file_name == '404.md':
            # 404 页面立即生成，并更新清单
            special_post = { 
                **metadata, 'content_html': content_html, 'toc_html': '', 
                'link': '404.html', 'footer_time_info': mod_time_cn
            }
            generator.generate_post_page(special_post)
            new_manifest[relative_path] = {'hash': current_hash, 'link': '404.html'}
            continue 

        if metadata.get('hidden') is True: 
            if slug == 'about' or file_name == config.ABOUT_PAGE:
                 # About 页面立即生成，并更新清单
                 special_post = { 
                     **metadata, 'content_html': content_html, 'toc_html': '', 
                     'link': 'about.html', 'footer_time_info': mod_time_cn
                 }
                 generator.generate_page_html(
                     special_post['content_html'], special_post['title'], 
                     'about', 'about.html', special_post['footer_time_info']
                 )
                 print(f"   -> [Special] Generating about.html (Hidden)")
            
            # Hidden 页面不加入列表
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
        
        # 检查 Slug 是否变化 (影响列表页和旧文件清理)
        if old_link and old_link != post_link and not needs_full_build:
            posts_data_changed = True
            print(f"   -> [SLUG CHANGED] {os.path.basename(md_file)}. Rebuilding all list pages.")
            
        # 收集标签 (用于列表页)
        for tag_data in post.get('tags', []):
            tag_map[tag_data['name']].append(post)
            
        parsed_posts.append(post)
        
        # 5. 更新 Manifest 和 posts_to_build 列表
        new_manifest[relative_path] = {'hash': current_hash, 'link': post_link}
        
        if needs_full_build or (old_link and old_link != post_link):
            # 如果内容变化，或者 Slug 变化，都需要重新生成 HTML
            posts_to_build.append(post) 
            
        # 如果 Slug 变化，删除旧的 HTML 文件
        if old_link and old_link != post_link and old_link != 'hidden' and old_link != '404.html':
             old_html_path = os.path.join(config.BUILD_DIR, old_link.strip('/'))
             if os.path.exists(old_html_path):
                os.remove(old_html_path)
                print(f"   -> [CLEANUP] Deleted old HTML file: {old_html_path}")


    # 6. 清理被删除的源文件（Post Cleanup Logic）
    deleted_paths = set(old_manifest.keys()) - source_md_paths
    for deleted_path in deleted_paths:
        item = old_manifest[deleted_path]
        deleted_link = item.get('link')
        print(f"   -> [DELETED] Source file {deleted_path} removed.")
        posts_data_changed = True # 源文件删除，列表页必须重建
        
        # 删除对应的 HTML 文件 (如果不是特殊页面)
        if deleted_link and deleted_link != 'hidden' and deleted_link != '404.html':
            deleted_html_path = os.path.join(config.BUILD_DIR, deleted_link.strip('/'))
            if os.path.exists(deleted_html_path):
                os.remove(deleted_html_path)
                print(f"   -> [CLEANUP] Deleted post HTML file: {deleted_html_path}")
                

    # 排序 (用于列表页和 P/N 导航)
    final_parsed_posts = sorted(parsed_posts, key=lambda p: p['date'], reverse=True)
    
    print(f"   -> Successfully parsed {len(final_parsed_posts)} blog posts. ({len(posts_to_build)} HTML files rebuilt)")

    # -------------------------------------------------------------------------
    # 4. P/N Navigation Injection (必须在所有文章解析和排序后执行)
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
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------
    # 5. 生成 HTML (应用增量逻辑)
    # -------------------------------------------------------------
    print("\n[4/4] Generating HTML...")
    
    # 为列表/静态页面生成一个通用的网站构建时间 (UTC+8) (基于当前时间)
    now_utc = datetime.now(timezone.utc)
    now_utc8 = now_utc.astimezone(TIMEZONE_INFO)
    global_build_time_cn = f"网站构建时间: {now_utc8.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)"
    
    # 生成普通文章详情页 (只生成变动的)
    for post in posts_to_build:
        generator.generate_post_page(post) 

    # 生成列表页 (应用增量逻辑)
    # 首次构建 (old_manifest为空) 或文章数据有变化时，才重建列表页
    if not old_manifest or posts_data_changed:
        print("   -> [REBUILDING] Index, Archive, Tags, RSS (Post data changed)")
        
        generator.generate_index_html(final_parsed_posts, global_build_time_cn) 
        generator.generate_archive_html(final_parsed_posts, global_build_time_cn) 
        generator.generate_tags_list_html(tag_map, global_build_time_cn) 

        # 生成标签页
        for tag, posts in tag_map.items():
            sorted_tag = sorted(posts, key=lambda p: p['date'], reverse=True)
            generator.generate_tag_page(tag, sorted_tag, global_build_time_cn) 

        generator.generate_robots_txt()
        
        # Sitemap 和 RSS 使用经过过滤和排序的列表
        with open(os.path.join(config.BUILD_DIR, config.SITEMAP_FILE), 'w', encoding='utf-8') as f:
            f.write(generator.generate_sitemap(final_parsed_posts))
        with open(os.path.join(config.BUILD_DIR, config.RSS_FILE), 'w', encoding='utf-8') as f:
            f.write(generator.generate_rss(final_parsed_posts))
            
    else:
        print("   -> [SKIPPED] Index, Archive, Tags, RSS (No post data change)")

    # 6. 保存新的构建清单
    save_manifest(new_manifest)
    print("   -> Manifest file updated.")
    
    print("\n✅ BUILD COMPLETE")

if __name__ == '__main__':
    build_site()
