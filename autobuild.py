# autobuild.py

import os
import shutil
import glob
import hashlib
from typing import List, Dict, Any
from collections import defaultdict
from datetime import datetime, timezone # 确保导入 datetime, timezone

# 导入分离后的模块
import config
from parser import get_metadata_and_content, tag_to_slug 
import generator

# NEW: 用于增量构建的缓存
POST_CACHE = {}

# --- 辅助函数：计算文件哈希 ---
def hash_file(filepath: str) -> str:
    """计算文件的 SHA256 哈希值的前8位"""
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()[:8]
    except FileNotFoundError:
        print(f"Warning: File not found for hashing: {filepath}")
        return 'nohash'


# --- 主构建函数 ---

def build_site():
    """清理、解析、生成整个网站。"""
    
    print("--- 1. 清理和准备目录 ---")
    
    # 确保构建目录干净
    if os.path.exists(config.BUILD_DIR):
        print(f"Cleaning up old build directory: {config.BUILD_DIR}")
        # 不删除整个 _site，只删除动态生成的内容，保留旧的静态文件
        for item in os.listdir(config.BUILD_DIR):
            item_path = os.path.join(config.BUILD_DIR, item)
            # 保留 assets 目录（其中包含 style.css）和 STATIC_DIR/MEDIA_DIR
            if item != 'assets' and item != config.MEDIA_DIR and item != 'static':
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
    else:
        os.makedirs(config.BUILD_DIR)
        
    os.makedirs(config.POSTS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.TAGS_OUTPUT_DIR, exist_ok=True)
    
    # 复制静态文件（假设存在）
    generator.copy_static_files()
    
    # 复制媒体文件（如果存在）
    generator.copy_media_files()

    
    print("--- 2. 处理特殊页面 (如 about.md) ---")
    
    about_page_data = None # 初始化 about 页面数据
    about_md_path = config.ABOUT_MD_PATH # 'markdown/about.md'
    
    if os.path.exists(about_md_path):
        print(f"--- 2a. 解析特殊页面: {about_md_path} ---")
        # 使用 parser.py 来解析 about.md
        about_metadata, _, about_html, about_toc = get_metadata_and_content(about_md_path)
        
        if about_metadata and about_html:
            # 确保 about 页面有 title, link, content_html, hidden
            about_page_data = {
                'title': about_metadata.get('title', '关于我'), # 默认标题
                'date': about_metadata.get('date', datetime.now(timezone.utc)), # 使用当前时间作为默认日期
                'link': f"/{config.ABOUT_OUTPUT_FILE}", # 明确指定 link 为 /about.html
                'content_html': about_html,
                'toc_html': about_toc,
                'hidden': about_metadata.get('hidden', False) # 默认不隐藏
            }
            # 2b. 生成 about.html
            generator.generate_about_page(about_page_data)
            print(f"SUCCESS: Generated about page at {config.ABOUT_OUTPUT_FILE}.")
        else:
             print(f"WARNING: Skipping {about_md_path} due to parsing error or empty content.")
    else:
        # 提示用户
        print("INFO: 'markdown/about.md' 不存在。如果要创建网站根目录的 'about.html' 页面，请在 'markdown/' 目录下创建 'about.md' 文件并添加必要的 YAML Frontmatter (如 title)。")
    
    
    print("--- 3. 解析所有文章 ---")
    
    parsed_posts = [] 
    md_files = glob.glob(os.path.join(config.MD_DIR, '*.md'))
    for md_file in md_files:
        # 忽略 about.md，因为它已经被单独处理
        if os.path.basename(md_file).lower() == 'about.md':
            continue 
            
        # --- (此处应为解析文章内容的原始逻辑，确保捕获 'hidden' 字段) ---
        # 假设原始逻辑在这里解析文章并添加到 parsed_posts
        try:
            metadata, content_markdown, content_html, toc_html = get_metadata_and_content(md_file)
            if not metadata or not content_html:
                continue
            
            # 假设 slug, link, date 等字段已处理
            # 确保 hidden 字段被捕获
            post_data = {
                'title': metadata.get('title', 'No Title'),
                'date': metadata.get('date', datetime.now(timezone.utc)),
                'link': metadata.get('link', f"/{config.POSTS_DIR}/{metadata.get('slug', 'no-slug')}.html"), # 简化
                'content_html': content_html,
                'toc_html': toc_html,
                'tags': metadata.get('tags', []),
                'hidden': metadata.get('hidden', False) # 确保 hidden 字段被捕获
            }
            parsed_posts.append(post_data)
        except Exception as e:
            print(f"Error parsing post file {md_file}: {e}")
        # --- (原始逻辑结束) ---
        
    print(f"Parsed {len(parsed_posts)} post files.")
    
    print("--- 4. 生成 HTML 页面 ---")
    
    # 4a. 对所有文章按日期排序
    final_parsed_posts = sorted(
        parsed_posts, 
        key=lambda p: p['date'], 
        reverse=True
    )
    print(f"Total {len(final_parsed_posts)} posts loaded.")

    # NEW: 过滤出可见文章用于列表页 (首页、归档、标签)
    visible_posts = [p for p in final_parsed_posts if not generator.is_post_hidden(p)]
    print(f"Total {len(visible_posts)} visible posts (not marked 'hidden: true').")

    # 4b. 生成首页 (MODIFIED: 使用可见文章列表)
    generator.generate_index_html(visible_posts)

    # 4c. 生成归档页 (MODIFIED: 使用可见文章列表)
    generator.generate_archive_html(visible_posts)

    # 4d. 生成标签页 (tag_map 仍然从所有文章中生成，但 generator 内部函数会过滤)
    tag_map = defaultdict(list)
    for post in final_parsed_posts:
        # 兼容性处理：tag 可能是字符串或包含 name 的字典
        tags_list = post.get('tags', [])
        if isinstance(tags_list, list):
            for tag_data in tags_list:
                tag_name = tag_data.get('name') if isinstance(tag_data, dict) else tag_data
                if tag_name:
                    tag_map[tag_name].append(post)

    # 4d-1. 生成所有标签的列表页 (tags.html)
    generator.generate_tags_list_html(tag_map) 

    # 4d-2. 为每个标签生成单独页面
    for tag, posts in tag_map.items():
        # 按日期排序该标签下的所有文章 (包括隐藏的)
        sorted_tag_posts = sorted(
            posts, 
            key=lambda p: p['date'], 
            reverse=True
        )
        # generate_tag_page 内部会过滤隐藏文章
        generator.generate_tag_page(tag, sorted_tag_posts) 
        
    print(f"Generated {len(tag_map)} tag pages.")

    # 4e. 生成单篇文章 HTML
    for post in final_parsed_posts:
        generator.generate_post_html(post)

    print("--- 5. 生成 XML 文件 ---")
    
    # 5a. robots.txt
    generator.generate_robots_txt()
    
    # 5b. sitemap.xml (MODIFIED: 只包含可见文章和可见的 about 页面)
    # 收集所有需要收录到 Sitemap 的项目
    sitemap_items = visible_posts[:]
    
    # 如果 about.html 是可见的（即 not hidden: true），则添加到 sitemap_items
    if about_page_data and not about_page_data.get('hidden', False):
         sitemap_items.append(about_page_data)
        
    sitemap_content = generator.generate_sitemap(sitemap_items)
    try:
        output_path = os.path.join(config.BUILD_DIR, config.SITEMAP_FILE)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(sitemap_content)
        print(f"SUCCESS: Generated {config.SITEMAP_FILE}.")
    except Exception as e:
        print(f"Error generating sitemap.xml: {type(e).__name__}: {e}")
        
    # 5c. rss.xml (MODIFIED: 只包含可见文章)
    rss_xml_content = generator.generate_rss(visible_posts) # 传递可见文章
    try:
        output_path = os.path.join(config.BUILD_DIR, config.RSS_FILE)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(rss_xml_content)
        print(f"SUCCESS: Generated {config.RSS_FILE}.")
    except Exception as e:
        print(f"Error generating rss.xml: {type(e).__name__}: {e}")
