# autobuild.py

import os
import shutil
import glob
from typing import List, Dict, Any
from collections import defaultdict

# 导入分离后的模块
import config
# 关键修正：确保 parser 模块被正确导入
from parser import get_metadata_and_content, tag_to_slug 
import generator

# --- 主构建函数 ---

def build_site():
    """清理、解析、生成整个网站。"""
    
    print("--- 1. 清理和准备目录 ---")
    
    # 确保构建目录干净
    if os.path.exists(config.BUILD_DIR):
        print(f"Cleaning up old build directory: {config.BUILD_DIR}")
        shutil.rmtree(config.BUILD_DIR)
    
    # 创建所有必需的目录
    os.makedirs(config.POSTS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.TAGS_OUTPUT_DIR, exist_ok=True)
    
    # 复制静态文件
    # 注意: 这里假定 assets 和 static 目录位于 autobuild.py 旁边
    for src_dir, dest_dir in [('assets', config.BUILD_DIR), ('static', config.STATIC_OUTPUT_DIR), ('media', config.MEDIA_OUTPUT_DIR)]:
        if os.path.exists(src_dir):
            try:
                # 目标目录已经存在，所以我们只复制内容
                if src_dir == 'assets': # 复制 assets 到 _site 根目录
                    shutil.copytree(src_dir, os.path.join(config.BUILD_DIR, src_dir), dirs_exist_ok=True)
                else:
                    shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)
                print(f"SUCCESS: Copied {src_dir} to {os.path.basename(dest_dir)}")
            except Exception as e:
                print(f"Error copying {src_dir}: {e}")
        else:
            print(f"Warning: Source directory '{src_dir}' not found.")
            
    print("--- 2. 解析 Markdown 文件 ---")
    
    # 查找所有 Markdown 文件
    # 查找所有 .md 文件，包括 MD_DIR 目录下的文件
    markdown_files = glob.glob(os.path.join(config.MD_DIR, '**', '*.md'), recursive=True)
    
    if not markdown_files:
        print("Warning: No Markdown files found. Site will be built without content.")

    parsed_posts = []
    tag_map = defaultdict(list) # 用于标签页生成
    
    for md_file in markdown_files:
        post_data = {}
        
        # 关键修正：接收 parser.py 返回的全部四个值
        metadata, content_markdown, content_html, toc_html = get_metadata_and_content(md_file)
        
        # 跳过没有标题的文章，或者跳过设置了 draft: true 的文章
        if not metadata.get('title') or metadata.get('draft') is True:
            # print(f"Skipping draft or untitled post: {md_file}") # 调试行，可移除
            continue
        
        # --- 核心数据映射 ---
        
        # 1. 标题和内容
        post_data.update(metadata)
        post_data['content_markdown'] = content_markdown
        post_data['content_html'] = content_html
        # 关键修正：存储 TOC HTML
        post_data['toc_html'] = toc_html
        
        # 2. 生成 slug
        # 优先使用 metadata 中的 slug，否则使用文件名作为 slug
        base_name = os.path.splitext(os.path.basename(md_file))[0]
        post_data['slug'] = metadata.get('slug', base_name)
        
        # 3. 处理分类 (可选)
        # 暂时不支持复杂的分类，仅支持 posts/slug.html 结构
        
        # 4. 存储到全局列表
        parsed_posts.append(post_data)
        
        # 5. 建立标签映射
        for tag_info in post_data['tags']:
            # tag_info 是 {'name': '...', 'slug': '...'} 结构
            tag_map[tag_info['slug']].append(post_data)


    # 按日期降序排列所有文章
    final_parsed_posts = sorted(
        parsed_posts, 
        key=lambda p: p['date'], 
        reverse=True
    )
    
    print(f"SUCCESS: Parsed {len(final_parsed_posts)} Markdown files.")
    
    print("--- 3. 生成文章详情页 ---")
    
    # 3a. 生成每一篇文章的 HTML 文件
    for post in final_parsed_posts:
        generator.generate_post_html(post)
        
    print(f"Generated {len(final_parsed_posts)} post detail pages.")
        
    print("--- 4. 生成通用页面和列表页 ---")
    
    # 4a. 首页 (index.html) - 只显示最新的几篇文章
    generator.generate_index_html(final_parsed_posts)
    
    # 4b. 归档页 (archive.html) - 显示所有文章
    generator.generate_archive_html(final_parsed_posts)
    
    # 4c. 关于页 (about.html) - 独立文章
    # 假定 about.md 总是存在 (在 MD_DIR 根目录)
    about_md_path = os.path.join(config.MD_DIR, 'about.md')
    if os.path.exists(about_md_path):
        # 关键修正：接收 parser.py 返回的全部四个值
        about_meta, about_md, about_html, about_toc = get_metadata_and_content(about_md_path)
        # 将 about.md 视为一个特殊的 post 对象
        about_post = {
            'title': about_meta.get('title', '关于'),
            'content_html': about_html,
            'canonical_url': generator.make_internal_url(config.ABOUT_FILE), # 修正: about 页面使用自身的 url
            # MODIFIED: 传递 toc_html 以防 about.md 中有目录
            'toc_html': about_toc
        }
        generator.generate_about_html(about_post)
        print(f"Generated {config.ABOUT_FILE}.")
    else:
        print(f"Warning: {config.MD_DIR}/about.md not found. Skipping about page generation.")

    # 4d. 标签页
    
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

    
    print("\\n--- 🎉 网站构建完成！ ---")
    print(f"输出目录: {config.BUILD_DIR}")


if __name__ == '__main__':
    build_site()
