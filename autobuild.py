
# autobuild.py

import os
import shutil
import glob
import hashlib
from typing import List, Dict, Any
from collections import defaultdict

# 导入分离后的模块
import config
from parser import get_metadata_and_content, tag_to_slug 
import generator

# --- 自检环节：检查 Pygments 是否安装 ---
try:
    import pygments
    print(f"CHECK: Pygments found (version {pygments.__version__}). Code highlighting should work.")
except ImportError:
    print("!!!! CRITICAL WARNING !!!!")
    print("Pygments library is NOT installed.")
    print("Code blocks will NOT be highlighted.")
    print("Please run: pip install Pygments")
    print("!!!! CRITICAL WARNING !!!!")
# ------------------------------------


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
    
    if os.path.exists(config.BUILD_DIR):
        print(f"Cleaning up old build directory: {config.BUILD_DIR}")
        for item in os.listdir(config.BUILD_DIR):
            item_path = os.path.join(config.BUILD_DIR, item)
            if item not in ['assets', config.STATIC_DIR, config.MEDIA_DIR]:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
    
    os.makedirs(config.POSTS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.TAGS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.STATIC_OUTPUT_DIR, exist_ok=True) 
    
    # 1b. 处理静态文件
    assets_dir = os.path.join(config.BUILD_DIR, 'assets')
    os.makedirs(assets_dir, exist_ok=True)
    
    if os.path.exists(config.STATIC_DIR):
        print(f"Copying static files from {config.STATIC_DIR} to {config.STATIC_OUTPUT_DIR}")
        shutil.copytree(config.STATIC_DIR, config.STATIC_OUTPUT_DIR, dirs_exist_ok=True)
    
    # NEW: 处理 style.css 的哈希和复制
    css_source_path = 'assets/style.css'
    if os.path.exists(css_source_path):
        css_hash = hash_file(css_source_path)
        new_css_filename = f"style.{css_hash}.css"
        # 更新全局配置中的文件名
        config.CSS_FILENAME = new_css_filename
        css_dest_path = os.path.join(assets_dir, new_css_filename)
        shutil.copy2(css_source_path, css_dest_path)
        print(f"SUCCESS: Copied and hashed CSS to {new_css_filename}")
    else:
        config.CSS_FILENAME = 'style.css'
        print("Warning: assets/style.css not found. Using default CSS filename.")

    # 2. 查找 Markdown 文件
    print("--- 2. 查找和解析 Markdown 文件 ---")
    
    md_files = glob.glob(os.path.join(config.MARKDOWN_DIR, '*.md'))
    if not md_files:
        md_files = glob.glob('*.md')
    
    if not md_files:
        print("Error: No Markdown files found. Aborting build.")
        return

    parsed_posts: List[Dict[str, Any]] = []
    tag_map = defaultdict(list)
    
    for md_file in md_files:
        metadata, content_markdown, content_html, toc_html = get_metadata_and_content(md_file)
        
        if not all(k in metadata for k in ['date', 'title', 'slug']):
            print(f"Warning: Skipping file '{md_file}' - missing metadata.")
            continue
            
        post: Dict[str, Any] = {
            **metadata, 
            'content_markdown': content_markdown,
            'content_html': content_html,
            'toc_html': toc_html,
        }
        
        post_link = os.path.join(config.POSTS_DIR_NAME, f"{post['slug']}.html")
        post['link'] = post_link
        
        for tag_data in post.get('tags', []):
            tag_map[tag_data['name']].append(post)
            
        parsed_posts.append(post)

    # 3. 排序文章
    final_parsed_posts = sorted(parsed_posts, key=lambda p: p['date'], reverse=True)
    print(f"Successfully parsed {len(final_parsed_posts)} articles.")

    # 4. 生成 HTML 页面
    print("--- 3. 生成 HTML 页面 ---")
    
    for post in final_parsed_posts:
        generator.generate_post_page(post)
    
    generator.generate_index_html(final_parsed_posts)
    generator.generate_archive_html(final_parsed_posts)
    generator.generate_tags_list_html(tag_map)

    for tag, posts in tag_map.items():
        sorted_tag_posts = sorted(posts, key=lambda p: p['date'], reverse=True)
        generator.generate_tag_page(tag, sorted_tag_posts)

    # 5. 生成 XML
    generator.generate_robots_txt()
    
    sitemap_content = generator.generate_sitemap(final_parsed_posts)
    with open(os.path.join(config.BUILD_DIR, config.SITEMAP_FILE), 'w', encoding='utf-8') as f:
        f.write(sitemap_content)
        
    rss_xml_content = generator.generate_rss(final_parsed_posts)
    with open(os.path.join(config.BUILD_DIR, config.RSS_FILE), 'w', encoding='utf-8') as f:
        f.write(rss_xml_content)
        
    print("\n--- 网站构建完成！ ---")


if __name__ == '__main__':
    build_site()
