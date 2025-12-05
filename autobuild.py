# autobuild.py - Final Strict Version

import os
import shutil
import glob
import hashlib
from typing import List, Dict, Any
from collections import defaultdict

import config
from parser import get_metadata_and_content
import generator

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

def build_site():
    print("\n" + "="*40)
    print("   🚀 STARTING STRICT BUILD PROCESS")
    print("="*40 + "\n")
    
    # -------------------------------------------------------------
    # 1. 强力清理 (Force Clean)
    # -------------------------------------------------------------
    print("[1/4] Cleaning Workspace...")
    
    # 只要存在 _site 目录，无论里面有什么，全部铲除
    if os.path.exists(config.BUILD_DIR):
        print(f"   -> Removing directory: {config.BUILD_DIR}")
        shutil.rmtree(config.BUILD_DIR)
    
    # 重新建立空目录
    os.makedirs(config.BUILD_DIR)
    os.makedirs(config.POSTS_OUTPUT_DIR)
    os.makedirs(config.TAGS_OUTPUT_DIR)
    os.makedirs(config.STATIC_OUTPUT_DIR)
    print("   -> Workspace is now empty and clean.")

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
        print(f"   -> CSS Hashed: {new_css}")
    else:
        config.CSS_FILENAME = 'style.css'
        print("   -> Warning: style.css not found.")

    # -------------------------------------------------------------
    # 3. 解析 Markdown (Parsing)
    # -------------------------------------------------------------
    print("\n[3/4] Parsing Markdown Files...")
    
    # 获取所有 md 文件
    md_files = glob.glob(os.path.join(config.MARKDOWN_DIR, '*.md'))
    if not md_files: md_files = glob.glob('*.md')
    
    parsed_posts = []
    tag_map = defaultdict(list)
    
    # 记录解析到的文件名，用于调试
    parsed_slugs = []

    for md_file in md_files:
        metadata, content_md, content_html, toc_html = get_metadata_and_content(md_file)
        
        # 跳过 hidden 或无效文件
        if metadata.get('hidden') is True: continue
        if not all(k in metadata for k in ['date', 'title', 'slug']): continue
            
        post = {
            **metadata, 
            'content_markdown': content_md,
            'content_html': content_html,
            'toc_html': toc_html,
            'link': os.path.join(config.POSTS_DIR_NAME, f"{metadata['slug']}.html").replace('\\', '/')
        }
        
        for tag_data in post.get('tags', []):
            tag_map[tag_data['name']].append(post)
            
        parsed_posts.append(post)
        parsed_slugs.append(metadata['slug'])

    final_parsed_posts = sorted(parsed_posts, key=lambda p: p['date'], reverse=True)
    print(f"   -> Parsed {len(final_parsed_posts)} articles.")
    print(f"   -> Valid Slugs found: {parsed_slugs}") 
    # ^ 在 Cloudflare 日志里看这一行，确保删除的文章确实没出现在这里

    # -------------------------------------------------------------
    # 4. 生成与验证 (Generation & Verification)
    # -------------------------------------------------------------
    print("\n[4/4] Generating HTML...")
    
    # 生成文章
    for post in final_parsed_posts:
        generator.generate_post_page(post)
    
    # 生成列表
    generator.generate_index_html(final_parsed_posts)
    generator.generate_archive_html(final_parsed_posts)
    generator.generate_tags_list_html(tag_map)

    # 生成标签页
    for tag, posts in tag_map.items():
        sorted_tag = sorted(posts, key=lambda p: p['date'], reverse=True)
        generator.generate_tag_page(tag, sorted_tag)

    # 生成 Sitemap/RSS
    generator.generate_robots_txt()
    with open(os.path.join(config.BUILD_DIR, config.SITEMAP_FILE), 'w', encoding='utf-8') as f:
        f.write(generator.generate_sitemap(final_parsed_posts))
    with open(os.path.join(config.BUILD_DIR, config.RSS_FILE), 'w', encoding='utf-8') as f:
        f.write(generator.generate_rss(final_parsed_posts))
        
    print("\n" + "="*40)
    print(f"   ✅ BUILD SUCCESSFUL")
    print(f"   Output: {config.BUILD_DIR}/")
    print(f"   Total Generated: {len(final_parsed_posts)} posts")
    print("="*40 + "\n")

if __name__ == '__main__':
    build_site()
