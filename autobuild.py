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
    print("!!!! WARNING: Pygments not found. Code highlighting will be disabled. !!!!")


def hash_file(filepath: str) -> str:
    """计算文件的 SHA256 哈希值的前8位"""
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()[:8]
    except FileNotFoundError:
        return 'nohash'


def build_site():
    print("\n========================================")
    print("   🚀 Starting Fresh Build Process")
    print("========================================\n")
    
    # -------------------------------------------------------------
    # 1. 暴力清理 (Aggressive Clean)
    # -------------------------------------------------------------
    # Cloudflare 环境中有时会保留缓存，这里我们强制删除整个构建目录
    # 确保没有任何“僵尸”文件残留。
    # -------------------------------------------------------------
    print("--- 1. Cleaning Workspace ---")
    
    if os.path.exists(config.BUILD_DIR):
        print(f"   [Clean] Removing entire build directory: {config.BUILD_DIR}")
        try:
            shutil.rmtree(config.BUILD_DIR)
        except Exception as e:
            print(f"   [Error] Failed to clean build dir: {e}")
            # 如果删除失败（极少见），尝试手动清空内容
            for item in os.listdir(config.BUILD_DIR):
                path = os.path.join(config.BUILD_DIR, item)
                if item not in ['.git', 'CNAME']: # 保护 GitHub Pages 相关文件
                    if os.path.isdir(path): shutil.rmtree(path, ignore_errors=True)
                    else: os.remove(path)
    
    # 重新创建空目录
    os.makedirs(config.BUILD_DIR, exist_ok=True)
    os.makedirs(config.POSTS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.TAGS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.STATIC_OUTPUT_DIR, exist_ok=True) 
    
    print("   [Init] Build directories created.")

    # -------------------------------------------------------------
    # 2. 资源处理 (CSS Hash)
    # -------------------------------------------------------------
    print("\n--- 2. Processing Assets ---")
    assets_dir = os.path.join(config.BUILD_DIR, 'assets')
    os.makedirs(assets_dir, exist_ok=True)
    
    # 复制静态资源
    if os.path.exists(config.STATIC_DIR):
        shutil.copytree(config.STATIC_DIR, config.STATIC_OUTPUT_DIR, dirs_exist_ok=True)
    
    # 处理 CSS
    css_source_path = 'assets/style.css'
    if os.path.exists(css_source_path):
        css_hash = hash_file(css_source_path)
        new_css_filename = f"style.{css_hash}.css"
        config.CSS_FILENAME = new_css_filename # 更新配置
        
        shutil.copy2(css_source_path, os.path.join(assets_dir, new_css_filename))
        print(f"   [Asset] CSS hashed: {new_css_filename}")
    else:
        config.CSS_FILENAME = 'style.css'
        print("   [Warn] style.css not found, using default name.")

    # -------------------------------------------------------------
    # 3. 解析 Markdown (Core Logic)
    # -------------------------------------------------------------
    print("\n--- 3. Parsing Markdown ---")
    
    md_files = glob.glob(os.path.join(config.MARKDOWN_DIR, '*.md'))
    if not md_files: md_files = glob.glob('*.md') # 兼容模式
    
    parsed_posts: List[Dict[str, Any]] = []
    tag_map = defaultdict(list)
    
    for md_file in md_files:
        metadata, content_md, content_html, toc_html = get_metadata_and_content(md_file)
        
        # 过滤隐藏文章
        if metadata.get('hidden') is True: continue
        # 过滤无效文章
        if not all(k in metadata for k in ['date', 'title', 'slug']): continue
            
        post = {
            **metadata, 
            'content_markdown': content_md,
            'content_html': content_html,
            'toc_html': toc_html,
            # 统一路径分隔符，防止 Windows/Linux 路径差异
            'link': os.path.join(config.POSTS_DIR_NAME, f"{metadata['slug']}.html").replace('\\', '/')
        }
        
        tag_map_entries = post.get('tags', [])
        for tag_data in tag_map_entries:
            tag_map[tag_data['name']].append(post)
            
        parsed_posts.append(post)

    # 按日期排序
    final_parsed_posts = sorted(parsed_posts, key=lambda p: p['date'], reverse=True)
    print(f"   [Parsed] Processed {len(final_parsed_posts)} valid articles.")

    # -------------------------------------------------------------
    # 4. 生成 HTML (Generation)
    # -------------------------------------------------------------
    print("\n--- 4. Generating Pages ---")
    
    # 文章详情页
    for post in final_parsed_posts:
        generator.generate_post_page(post)
    
    # 列表页 (传入的列表中绝对不包含已删除的 MD 文件)
    generator.generate_index_html(final_parsed_posts)
    generator.generate_archive_html(final_parsed_posts)
    generator.generate_tags_list_html(tag_map)

    # 标签详情页
    for tag, posts in tag_map.items():
        sorted_tag = sorted(posts, key=lambda p: p['date'], reverse=True)
        generator.generate_tag_page(tag, sorted_tag)

    # 站点地图与RSS
    generator.generate_robots_txt()
    
    with open(os.path.join(config.BUILD_DIR, config.SITEMAP_FILE), 'w', encoding='utf-8') as f:
        f.write(generator.generate_sitemap(final_parsed_posts))
        
    with open(os.path.join(config.BUILD_DIR, config.RSS_FILE), 'w', encoding='utf-8') as f:
        f.write(generator.generate_rss(final_parsed_posts))
        
    print(f"\n✅ Build Complete! Output directory: {config.BUILD_DIR}/")
    print("========================================\n")


if __name__ == '__main__':
    build_site()
