# autobuild.py

import os
import shutil
import glob
import hashlib # NEW: 导入 hashlib 用于计算文件哈希
from typing import List, Dict, Any
from collections import defaultdict

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
            # 保留 assets 目录（其中包含 style.css）和 STATIC_DIR/MEDIA_DIR，后面单独处理
            if item not in ['assets', config.STATIC_DIR, config.MEDIA_DIR]:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
    
    # 确保 posts 和 tags 的输出目录存在
    # ！！！关键修正区：添加日志和错误检查，确保目录创建成功 ！！！
    try:
        os.makedirs(config.POSTS_OUTPUT_DIR, exist_ok=True)
        os.makedirs(config.TAGS_OUTPUT_DIR, exist_ok=True)
        print(f"SUCCESS: Ensured output directory exists: {config.POSTS_OUTPUT_DIR}")
        print(f"SUCCESS: Ensured output directory exists: {config.TAGS_OUTPUT_DIR}")
    except OSError as e:
        print(f"FATAL ERROR: Failed to create output directories. Check filesystem permissions.")
        print(f"Error details: {e}")
        return # 目录创建失败，停止后续构建
    # ！！！修正区结束 ！！！

    # 1b. 处理静态文件 (包括 CSS 和其他静态资源)
    # 确保 assets 目录存在
    assets_dir = os.path.join(config.BUILD_DIR, 'assets')
    os.makedirs(assets_dir, exist_ok=True)
    
    # 复制静态文件（如果存在）
    if os.path.exists(config.STATIC_DIR):
        print(f"Copying static files from {config.STATIC_DIR} to {config.STATIC_OUTPUT_DIR}")
        # 复制整个静态目录到 BUILD_DIR
        shutil.copytree(config.STATIC_DIR, config.STATIC_OUTPUT_DIR, dirs_exist_ok=True)
    
    # NEW: 处理 style.css 的哈希和复制
    css_source_path = 'assets/style.css'
    if os.path.exists(css_source_path):
        # 1. 计算哈希
        css_hash = hash_file(css_source_path)
        # 2. 生成带哈希的新文件名
        new_css_filename = f"style.{css_hash}.css"
        # 3. 更新 config.CSS_FILENAME 变量（关键步骤）
        config.CSS_FILENAME = new_css_filename
        # 4. 复制并重命名 CSS 文件到 _site/assets/
        css_dest_path = os.path.join(assets_dir, new_css_filename)
        shutil.copy2(css_source_path, css_dest_path)
        print(f"SUCCESS: Copied and hashed CSS to {new_css_filename}")
    else:
        # 如果 style.css 不存在，使用默认文件名
        config.CSS_FILENAME = 'style.css'
        print("Warning: assets/style.css not found. Using default CSS filename.")

    # 2. 查找 Markdown 文件
    print("--- 2. 查找和解析 Markdown 文件 ---")
    
    # 查找所有 .md 文件，优先从 config.MD_DIR 查找，如果不存在，则从根目录查找
    md_files = glob.glob(os.path.join(config.MD_DIR, '*.md'))
    if not md_files:
        md_files = glob.glob('*.md')
    
    if not md_files:
        print("Error: No Markdown files found in 'markdown/' or root directory. Aborting build.")
        return

    parsed_posts: List[Dict[str, Any]] = []
    tag_map = defaultdict(list) # 存储 {tag: [post1, post2, ...]}
    
    for md_file in md_files:
        # 2a. 解析文件内容
        metadata, content_markdown, content_html, toc_html = get_metadata_and_content(md_file)
        
        # 检查是否成功解析到元数据 (如缺少 date/title/slug 则跳过)
        if not all(k in metadata for k in ['date', 'title', 'slug']):
            print(f"Warning: Skipping file '{md_file}' due to missing critical metadata (date, title, or slug).")
            continue
            
        # 2b. 构造文章对象
        post: Dict[str, Any] = {
            # 将所有元数据放入 post 对象
            **metadata, 
            'content_markdown': content_markdown,
            'content_html': content_html,
            'toc_html': toc_html,
        }
        
        # 2c. 构造文章链接
        # 链接格式: posts/{slug}.html
        post_link = os.path.join(config.POSTS_DIR, f"{post['slug']}.html")
        post['link'] = post_link
        
        # 2d. 汇总标签
        # 注意：这里假设 parser.py 返回的 tags 已经是 name/slug 字典列表
        for tag_data in post.get('tags', []):
            # 使用 tag_data['name'] 作为 tag_map 的键
            tag_map[tag_data['name']].append(post)
            
        parsed_posts.append(post)

    # 3. 排序文章 (按日期降序)
    print("--- 3. 排序和最终处理文章 ---")
    final_parsed_posts = sorted(
        parsed_posts, 
        key=lambda p: p['date'], 
        reverse=True
    )
    
    print(f"Successfully parsed {len(final_parsed_posts)} articles.")

    # 4. 生成 HTML 页面
    print("--- 4. 生成 HTML 页面 ---")
    
    # 4a. 生成所有单篇文章页
    for post in final_parsed_posts:
        generator.generate_post_html(post)
    print(f"Generated {len(final_parsed_posts)} post pages.")
    
    # 4b. 生成首页
    generator.generate_index_html(final_parsed_posts)
    
    # 4c. 生成归档页
    generator.generate_archive_html(final_parsed_posts)
    
    # 4d. 生成标签页
    
    # 4d-1. 生成所有标签的列表页 (tags.html)
    generator.generate_tags_list_html(tag_map)

    # 4d-2. 为每个标签生成单独页面
    for tag, posts in tag_map.items():
        # 按日期排序该标签下的文章
        sorted_tag_posts = sorted(
            posts, 
            key=lambda p: p['date'], 
            reverse=True
        )
        generator.generate_tag_page(tag, sorted_tag_posts)
        
    print(f"Generated {len(tag_map)} tag pages.")


    print("--- 5. 生成 XML 文件 ---")
    
    # 5a. robots.txt
    generator.generate_robots_txt()
    
    # 5b. sitemap.xml
    sitemap_content = generator.generate_sitemap(final_parsed_posts)
    try:
        output_path = os.path.join(config.BUILD_DIR, config.SITEMAP_FILE)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(sitemap_content)
        print(f"SUCCESS: Generated {config.SITEMAP_FILE}.")
    except Exception as e:
        print(f"Error generating sitemap.xml: {type(e).__name__}: {e}")
        
    # 5c. rss.xml
    rss_xml_content = generator.generate_rss(final_parsed_posts)
    try:
        output_path = os.path.join(config.BUILD_DIR, config.RSS_FILE)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(rss_xml_content)
        print(f"SUCCESS: Generated {config.RSS_FILE}.")
    except Exception as e:
        print(f"Error generating rss.xml: {type(e).__name__}: {e}")
        
    print("\n--- 网站构建完成！ ---")


if __name__ == '__main__':
    build_site()
