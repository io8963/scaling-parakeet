# autobuild.py - Fixed 404 Logic

import os
import shutil
import glob
import hashlib
from typing import List, Dict, Any
from collections import defaultdict
from datetime import datetime, timezone, timedelta # [修改] 导入 timezone, timedelta

import config
from parser import get_metadata_and_content
import generator

# [新增] 定义 UTC+8 时区信息
TIMEZONE_OFFSET = timedelta(hours=8)
TIMEZONE_INFO = timezone(TIMEZONE_OFFSET)

# --- 检查依赖 ---
try:
    import pygments
except ImportError:
    pass

def hash_file(filepath: str) -> str:
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            hasher.update(f.read())
        return hasher.hexdigest()[:8]
    except FileNotFoundError:
        return 'nohash'

# [修改 FUNCTION] 获取文件的最后修改时间并格式化为 UTC+8
def format_file_mod_time(filepath: str) -> str:
    """获取文件的最后修改时间并格式化为中文构建时间 (UTC+8)。"""
    try:
        mtime_timestamp = os.path.getmtime(filepath)
        # 1. 获取 UTC datetime 对象 (从时间戳)
        mtime_dt_utc = datetime.fromtimestamp(mtime_timestamp, timezone.utc)
        # 2. 转换为 UTC+8
        mtime_dt_utc8 = mtime_dt_utc.astimezone(TIMEZONE_INFO)
        # 3. 格式化并标记时区
        return f"本文构建时间: {mtime_dt_utc8.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)"
    except FileNotFoundError:
        # 对于非Markdown生成的页面（如 index, archive），使用当前构建时间
        now_utc = datetime.now(timezone.utc)
        now_utc8 = now_utc.astimezone(TIMEZONE_INFO)
        return f"最新构建时间: {now_utc8.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)"
    except Exception:
         # 异常时的安全回退
         return f"最新构建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"


def build_site():
    print("\n" + "="*40)
    print("   🚀 STARTING BUILD PROCESS (Fix 404 List Issue & Hidden Pages)")
    print("="*40 + "\n")
    
    # -------------------------------------------------------------
    # 1. 清理工作区
    # -------------------------------------------------------------
    print("[1/4] Cleaning Workspace...")
    if os.path.exists(config.BUILD_DIR):
        shutil.rmtree(config.BUILD_DIR)
    
    os.makedirs(config.BUILD_DIR)
    os.makedirs(config.POSTS_OUTPUT_DIR)
    os.makedirs(config.TAGS_OUTPUT_DIR)
    os.makedirs(config.STATIC_OUTPUT_DIR)

    # -------------------------------------------------------------
    # 2. 资源处理
    # -------------------------------------------------------------
    print("\n[2/4] Processing Assets...")
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

    # -------------------------------------------------------------
    # 3. 解析 Markdown (关键修复部分)
    # -------------------------------------------------------------
    print("\n[3/4] Parsing Markdown Files...")
    
    md_files = glob.glob(os.path.join(config.MARKDOWN_DIR, '*.md'))
    if not md_files: md_files = glob.glob('*.md')
    
    parsed_posts = []
    tag_map = defaultdict(list)

    for md_file in md_files:
        metadata, content_md, content_html, toc_html = get_metadata_and_content(md_file)
        
        # 自动补全 slug
        if 'slug' not in metadata:
            # 如果没有 slug，用文件名
            filename_slug = os.path.splitext(os.path.basename(md_file))[0]
            metadata['slug'] = filename_slug

        slug = str(metadata['slug']).lower()
        file_name = os.path.basename(md_file)
        
        # [NEW] 获取当前 MD 文件的修改时间
        mod_time_cn = format_file_mod_time(md_file)

        # -------------------------------------------------------
        # [关键修复] 404 页面拦截器
        # 只要 slug 是 404 或者文件名是 404.md，立即单独处理
        # -------------------------------------------------------
        if slug == '404' or file_name == '404.md':
            print(f"   -> [Special] Generating 404.html (Excluded from list)")
            
            # 构造特殊数据对象
            special_post = {
                **metadata, 
                'content_markdown': content_md,
                'content_html': content_html,
                'toc_html': '', 
                'link': '404.html', # 强制指定输出到根目录
                'footer_time_info': mod_time_cn # [NEW] 注入构建时间
            }
            # 立即生成文件
            generator.generate_post_page(special_post)
            
            # ！！！关键：continue 跳过，绝对不加入 parsed_posts 列表！！！
            continue 
        # -------------------------------------------------------

        # 过滤 hidden 标记的文章 (双重保险)
        if metadata.get('hidden') is True: 
            # 如果是 hidden，检查是否是 about 页面
            if slug == 'about' or file_name == config.ABOUT_PAGE:
                 special_post = { 
                     **metadata, 
                     'content_html': content_html, 
                     'toc_html': '', 
                     'link': 'about.html',
                     'footer_time_info': mod_time_cn # [NEW] 注入构建时间
                 }
                 # [MODIFIED] generate_page_html 现在需要 footer_time_info 参数
                 generator.generate_page_html(
                     special_post['content_html'], 
                     special_post['title'], 
                     'about', 
                     'about.html',
                     special_post['footer_time_info']
                 )
                 print(f"   -> [Special] Generating about.html (Hidden)")
            
            # Hidden 页面不加入列表
            continue 

        # 检查普通文章的必要字段
        if not all(k in metadata for k in ['date', 'title']): 
            continue
            
        # 普通文章处理
        post = {
            **metadata, 
            'content_markdown': content_md,
            'content_html': content_html,
            'toc_html': toc_html,
            'link': os.path.join(config.POSTS_DIR_NAME, f"{slug}.html").replace('\\', '/'),
            'footer_time_info': mod_time_cn # [NEW] 注入构建时间
        }
        
        # 收集标签
        for tag_data in post.get('tags', []):
            tag_map[tag_data['name']].append(post)
            
        parsed_posts.append(post)

    # 排序
    final_parsed_posts = sorted(parsed_posts, key=lambda p: p['date'], reverse=True)
    print(f"   -> Successfully parsed {len(final_parsed_posts)} blog posts.")

    # -------------------------------------------------------------------------
    # [新增逻辑] 注入上/下一篇文章导航数据 (P/N Navigation Injection)
    # -------------------------------------------------------------------------
    for i, post in enumerate(final_parsed_posts):
        # i-1 是前一个元素 (时间上更近) -> Newer Article
        prev_post_data = final_parsed_posts[i - 1] if i > 0 else None
        
        # i+1 是后一个元素 (时间上更远) -> Older Article
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
    # 4. 生成 HTML
    # -------------------------------------------------------------
    print("\n[4/4] Generating HTML...")
    
    # [修改] 为列表/静态页面生成一个通用的网站构建时间 (UTC+8)
    now_utc = datetime.now(timezone.utc)
    now_utc8 = now_utc.astimezone(TIMEZONE_INFO)
    global_build_time_cn = f"网站构建时间: {now_utc8.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)"
    
    # 生成普通文章详情页
    for post in final_parsed_posts:
        generator.generate_post_page(post) # Post 已经带有 footer_time_info

    # [MODIFIED] 列表页现在需要 global_build_time_cn 参数
    generator.generate_index_html(final_parsed_posts, global_build_time_cn)
    generator.generate_archive_html(final_parsed_posts, global_build_time_cn)
    generator.generate_tags_list_html(tag_map, global_build_time_cn)

    # 生成标签页
    for tag, posts in tag_map.items():
        sorted_tag = sorted(posts, key=lambda p: p['date'], reverse=True)
        # [MODIFIED] 标签详情页也使用 global_build_time_cn
        generator.generate_tag_page(tag, sorted_tag, global_build_time_cn)

    generator.generate_robots_txt()
    
    # Sitemap 和 RSS 使用经过过滤和排序的列表
    with open(os.path.join(config.BUILD_DIR, config.SITEMAP_FILE), 'w', encoding='utf-8') as f:
        f.write(generator.generate_sitemap(final_parsed_posts))
    with open(os.path.join(config.BUILD_DIR, config.RSS_FILE), 'w', encoding='utf-8') as f:
        f.write(generator.generate_rss(final_parsed_posts))
        
    print("\n✅ BUILD COMPLETE")

if __name__ == '__main__':
    build_site()
