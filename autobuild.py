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
            # 保留 assets 目录（其中包含 style.css），后面单独处理
            if item not in ['assets', config.STATIC_DIR, config.MEDIA_DIR]: 
                 if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                 else:
                    os.remove(item_path)

    
    # 创建所有必需的目录
    os.makedirs(config.POSTS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.TAGS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(config.BUILD_DIR, 'assets'), exist_ok=True) # 确保 assets 目录存在
    
    # NEW: 优化 4 - 资产指纹/哈希
    print("Calculating asset hash...")
    style_css_path = os.path.join('assets', 'style.css')
    asset_hash = hash_file(style_css_path)
    # 将哈希值存入配置，供 generator.py 使用
    config.ASSET_HASH = asset_hash
    # 创建带哈希的文件名
    hashed_css_filename = f"style.{asset_hash}.css"
    hashed_css_path = os.path.join(config.BUILD_DIR, 'assets', hashed_css_filename)
    
    # 复制静态文件，包括带哈希的 CSS
    print("Copying static assets...")
    # 1. 复制 style.css 到带哈希的新文件
    try:
        shutil.copy2(style_css_path, hashed_css_path)
        # 将带哈希的 CSS 文件名存入配置，供 generator 引用
        config.CSS_FILENAME = hashed_css_filename
        print(f"SUCCESS: Copied {style_css_path} to {hashed_css_path}")
    except FileNotFoundError:
        print(f"ERROR: Cannot find required file {style_css_path}")
        config.CSS_FILENAME = 'style.css' # 保底
    
    # 2. 复制其他静态/媒体文件
    for src_dir, dest_dir in [('static', config.STATIC_OUTPUT_DIR), ('media', config.MEDIA_OUTPUT_DIR)]:
        if os.path.exists(src_dir):
            try:
                # 目标目录已经存在，所以我们只复制内容
                shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)
                print(f"Copied {src_dir} content to {dest_dir}.")
            except Exception as e:
                print(f"Error copying {src_dir}: {e}")

    print("--- 2. 解析 Markdown 文件 ---")

    md_files = glob.glob(os.path.join(config.MD_DIR, '*.md'))
    parsed_posts: List[Dict[str, Any]] = []
    about_post: Dict[str, Any] = {}
    total_parsed = 0
    skipped_posts = 0

    for md_file in md_files:
        post_slug = os.path.splitext(os.path.basename(md_file))[0]
        output_path = os.path.join(config.POSTS_OUTPUT_DIR, f'{post_slug}.html')
        
        # NEW: 优化 3 - 增量构建逻辑
        is_updated = True
        try:
            md_mtime = os.path.getmtime(md_file)
            if os.path.exists(output_path):
                html_mtime = os.path.getmtime(output_path)
                if md_mtime <= html_mtime:
                    # 如果 Markdown 文件修改时间不晚于 HTML 文件，则跳过解析
                    is_updated = False
                    skipped_posts += 1
        except Exception as e:
             # 如果获取时间戳失败，为了安全起见，重新解析
             print(f"Warning: Failed to get mtime for {md_file}. Rebuilding. Error: {e}")
             is_updated = True
             
        if not is_updated:
            continue # 跳过未更新的文件

        # 仅解析需要更新的文件
        metadata, content_markdown, content_html, toc_html = get_metadata_and_content(md_file)
        
        if not metadata:
            print(f"Skipping {md_file} due to empty/invalid metadata.")
            continue
            
        total_parsed += 1

        # 检查是否为 about 页面
        if post_slug.lower() == 'about':
            about_post = {
                'slug': post_slug,
                'title': metadata.get('title', '关于我'),
                'content_html': content_html,
                'toc_html': toc_html,
                # about 页面也需要日期用于 sitemap 等
                'date': metadata.get('date', None) 
            }
            continue

        # 处理常规文章
        post_data = {
            'slug': post_slug,
            'title': metadata.get('title', '无标题文章'),
            'date': metadata.get('date', None),
            'tags': metadata.get('tags', []),
            'content_markdown': content_markdown,
            'content_html': content_html,
            'toc_html': toc_html
        }
        
        parsed_posts.append(post_data)


    print(f"Parsed {total_parsed} updated post(s). Skipped {skipped_posts} unchanged post(s).")
    
    if not parsed_posts and not about_post:
        print("No content to build. Exiting.")
        return

    print("--- 3. 排序和数据整合 ---")
    
    # 3a. 按日期降序排序所有文章
    final_parsed_posts = sorted(
        parsed_posts, 
        key=lambda p: p['date'], 
        reverse=True
    )
    
    # 3b. 构建标签映射
    tag_map = defaultdict(list)
    for post in final_parsed_posts:
        for tag_data in post.get('tags', []):
            tag_map[tag_data['name']].append(post)

    print("--- 4. 生成通用页面和列表页 ---")

    # 4a. 生成所有文章详情页
    for post in final_parsed_posts:
        generator.generate_post_html(post)
        
    print(f"Generated {len(final_parsed_posts)} post files.")
    
    # 4b. 生成关于页面
    if about_post:
        generator.generate_about_html(about_post)
        print("Generated about page.")
    
    # 4c. 生成首页
    generator.generate_index_html(final_parsed_posts)
    
    # 4d. 生成归档页
    generator.generate_archive_html(final_parsed_posts)
    
    # 4e. 生成标签页
    
    # 4e-1. 生成所有标签的列表页 (tags.html)
    generator.generate_tags_list_html(tag_map)

    # 4e-2. 为每个标签生成单独页面
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

    print("--- 构建完成 ---")
    
if __name__ == '__main__':
    build_site()
