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
    # print(f"CHECK: Pygments found (version {pygments.__version__}).")
except ImportError:
    print("!!!! CRITICAL WARNING: Pygments library is NOT installed. Code blocks will NOT be highlighted. !!!!")

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
        return 'nohash'


# --- 主构建函数 ---

def build_site():
    """清理、解析、生成整个网站。"""
    
    print("\n========================================")
    print("   Starting Build Process... 🚀")
    print("========================================\n")
    
    # -------------------------------------------------------------
    # 1. 深度清理 (Deep Clean)
    # 核心逻辑：除了 'static' 和 'media' 这种大文件夹外，
    # 强制删除 posts, tags, assets 以及根目录下的 html/xml 文件。
    # 这确保了如果 Markdown 被删除了，对应的 HTML 也会彻底消失。
    # -------------------------------------------------------------
    print("--- 1. Cleaning up old build directory ---")
    
    if os.path.exists(config.BUILD_DIR):
        # 定义需要【保留】的文件夹（避免重复拷贝大文件）
        # 注意：.git 和 CNAME 是为了 GitHub Pages 部署保留的
        keep_list = [config.STATIC_DIR, config.MEDIA_DIR, '.git', 'CNAME']
        
        for item in os.listdir(config.BUILD_DIR):
            if item in keep_list:
                continue
            
            item_path = os.path.join(config.BUILD_DIR, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path) # 递归删除文件夹 (如 posts, tags, assets)
                    print(f"   [Deleted Dir]  {item}/")
                else:
                    os.remove(item_path)     # 删除文件 (如 index.html, archive.html)
                    # print(f"   [Deleted File] {item}")
            except Exception as e:
                print(f"   Error deleting {item}: {e}")
    else:
        os.makedirs(config.BUILD_DIR, exist_ok=True)
    
    # 重建基础目录结构
    os.makedirs(config.POSTS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.TAGS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.STATIC_OUTPUT_DIR, exist_ok=True) 
    
    # -------------------------------------------------------------
    # 2. 资源处理 (Assets & CSS)
    # 每次都重新处理 CSS，确保修改样式后哈希值更新
    # -------------------------------------------------------------
    print("\n--- 2. Processing Assets ---")
    assets_dir = os.path.join(config.BUILD_DIR, 'assets')
    os.makedirs(assets_dir, exist_ok=True)
    
    # 复制静态文件夹 (如果之前保留了，这里会自动跳过或覆盖)
    if os.path.exists(config.STATIC_DIR):
        # dirs_exist_ok=True 允许覆盖
        shutil.copytree(config.STATIC_DIR, config.STATIC_OUTPUT_DIR, dirs_exist_ok=True)
    
    # 处理 CSS 哈希
    css_source_path = 'assets/style.css'
    if os.path.exists(css_source_path):
        css_hash = hash_file(css_source_path)
        new_css_filename = f"style.{css_hash}.css"
        
        # 更新全局配置中的文件名，以便模板使用
        config.CSS_FILENAME = new_css_filename
        
        css_dest_path = os.path.join(assets_dir, new_css_filename)
        shutil.copy2(css_source_path, css_dest_path)
        print(f"   [CSS Generated] {new_css_filename}")
    else:
        config.CSS_FILENAME = 'style.css'
        print("   [Warning] assets/style.css not found.")

    # -------------------------------------------------------------
    # 3. 解析 Markdown (Parsing)
    # -------------------------------------------------------------
    print("\n--- 3. Parsing Markdown Files ---")
    
    md_files = glob.glob(os.path.join(config.MARKDOWN_DIR, '*.md'))
    if not md_files:
        # 兼容根目录模式
        md_files = glob.glob('*.md')
    
    if not md_files:
        print("   [Error] No Markdown files found. Aborting.")
        return

    parsed_posts: List[Dict[str, Any]] = []
    tag_map = defaultdict(list)
    
    for md_file in md_files:
        # 解析文件
        metadata, content_markdown, content_html, toc_html = get_metadata_and_content(md_file)
        
        # 跳过标记为 hidden: true 的文章 (用于草稿或特殊页面)
        if metadata.get('hidden') is True:
            # print(f"   [Skip] Hidden file: {os.path.basename(md_file)}")
            continue

        # 检查必要元数据
        if not all(k in metadata for k in ['date', 'title', 'slug']):
            print(f"   [Skip] Missing metadata in: {os.path.basename(md_file)}")
            continue
            
        post: Dict[str, Any] = {
            **metadata, 
            'content_markdown': content_markdown,
            'content_html': content_html,
            'toc_html': toc_html,
        }
        
        # 构建链接
        post_link = os.path.join(config.POSTS_DIR_NAME, f"{post['slug']}.html")
        post['link'] = post_link.replace('\\', '/') # 修复 Windows 路径分隔符
        
        # 收集标签
        for tag_data in post.get('tags', []):
            tag_map[tag_data['name']].append(post)
            
        parsed_posts.append(post)

    # 排序：按日期降序
    final_parsed_posts = sorted(parsed_posts, key=lambda p: p['date'], reverse=True)
    print(f"   [OK] Successfully parsed {len(final_parsed_posts)} articles.")

    # -------------------------------------------------------------
    # 4. 生成 HTML 页面 (Generating)
    # -------------------------------------------------------------
    print("\n--- 4. Generating HTML Pages ---")
    
    # 生成文章详情页
    for post in final_parsed_posts:
        generator.generate_post_page(post)
    
    # 生成列表页 (首页, 归档, 标签云)
    # 此时传入的 final_parsed_posts 已经是【不包含】已删除文件的最新列表
    generator.generate_index_html(final_parsed_posts)
    generator.generate_archive_html(final_parsed_posts)
    generator.generate_tags_list_html(tag_map)

    # 生成标签详情页
    for tag, posts in tag_map.items():
        sorted_tag_posts = sorted(posts, key=lambda p: p['date'], reverse=True)
        generator.generate_tag_page(tag, sorted_tag_posts)

    # 生成特殊文件
    generator.generate_robots_txt()
    
    # Sitemap & RSS
    sitemap_content = generator.generate_sitemap(final_parsed_posts)
    with open(os.path.join(config.BUILD_DIR, config.SITEMAP_FILE), 'w', encoding='utf-8') as f:
        f.write(sitemap_content)
        
    rss_xml_content = generator.generate_rss(final_parsed_posts)
    with open(os.path.join(config.BUILD_DIR, config.RSS_FILE), 'w', encoding='utf-8') as f:
        f.write(rss_xml_content)
        
    print(f"\n✅ Site built successfully in '{config.BUILD_DIR}' directory.")
    print(f"   Total Posts: {len(final_parsed_posts)}")
    print("========================================\n")


if __name__ == '__main__':
    build_site()
