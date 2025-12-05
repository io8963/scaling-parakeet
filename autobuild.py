# autobuild.py

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
    print("   🚀 STARTING BUILD PROCESS (With 404 Support)")
    print("="*40 + "\n")
    
    # -------------------------------------------------------------
    # 1. 强力清理
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
        print(f"   -> CSS Hashed: {new_css}")
    else:
        config.CSS_FILENAME = 'style.css'

    # -------------------------------------------------------------
    # 3. 解析 Markdown (核心修改部分)
    # -------------------------------------------------------------
    print("\n[3/4] Parsing Markdown Files...")
    
    md_files = glob.glob(os.path.join(config.MARKDOWN_DIR, '*.md'))
    if not md_files: md_files = glob.glob('*.md')
    
    parsed_posts = []
    tag_map = defaultdict(list)

    for md_file in md_files:
        metadata, content_md, content_html, toc_html = get_metadata_and_content(md_file)
        
        # 必须要有 slug
        if 'slug' not in metadata: continue
        
        slug = metadata['slug']
        
        # --- [新增逻辑] 特殊处理 404 页面 ---
        if slug == '404':
            # 1. 构造特殊路径：直接在根目录，不是 posts/
            special_post = {
                **metadata, 
                'content_markdown': content_md,
                'content_html': content_html,
                'toc_html': '', # 404页面一般不需要目录
                'link': '404.html' # 关键：生成到根目录
            }
            # 2. 立即生成文件
            generator.generate_post_page(special_post)
            print("   -> Generated specialized page: 404.html")
            # 3. continue，不把它加入文章列表
            continue
        # ----------------------------------

        # 普通文章处理：跳过 hidden
        if metadata.get('hidden') is True: continue
        
        # 检查必要字段
        if not all(k in metadata for k in ['date', 'title']): continue
            
        post = {
            **metadata, 
            'content_markdown': content_md,
            'content_html': content_html,
            'toc_html': toc_html,
            'link': os.path.join(config.POSTS_DIR_NAME, f"{slug}.html").replace('\\', '/')
        }
        
        for tag_data in post.get('tags', []):
            tag_map[tag_data['name']].append(post)
            
        parsed_posts.append(post)

    final_parsed_posts = sorted(parsed_posts, key=lambda p: p['date'], reverse=True)
    print(f"   -> Parsed {len(final_parsed_posts)} blog posts.")

    # -------------------------------------------------------------
    # 4. 生成 HTML
    # -------------------------------------------------------------
    print("\n[4/4] Generating HTML...")
    
    for post in final_parsed_posts:
        generator.generate_post_page(post)
    
    generator.generate_index_html(final_parsed_posts)
    generator.generate_archive_html(final_parsed_posts)
    generator.generate_tags_list_html(tag_map)

    for tag, posts in tag_map.items():
        sorted_tag = sorted(posts, key=lambda p: p['date'], reverse=True)
        generator.generate_tag_page(tag, sorted_tag)

    generator.generate_robots_txt()
    
    with open(os.path.join(config.BUILD_DIR, config.SITEMAP_FILE), 'w', encoding='utf-8') as f:
        f.write(generator.generate_sitemap(final_parsed_posts))
    with open(os.path.join(config.BUILD_DIR, config.RSS_FILE), 'w', encoding='utf-8') as f:
        f.write(generator.generate_rss(final_parsed_posts))
        
    print("\n✅ BUILD COMPLETE")

if __name__ == '__main__':
    build_site()
