# generator.py

import os
import shutil 
import glob   
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Dict, Any, Tuple 
from jinja2 import Environment, FileSystemLoader
import json 

# 导入配置
import config


# --- Jinja2 环境配置配置 ---
# 设置模板目录
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=True, # 开启自动转义，防止 XSS
    trim_blocks=True, # 自动去除块标签后的换行符
    lstrip_blocks=True # 自动去除块标签前的空白
)

# --- 辅助函数 ---

def tag_to_slug(tag_name: str) -> str:
    """将标签名转换为 URL 友好的 slug (小写，空格变'-')。"""
    return tag_name.lower().replace(' ', '-')

def get_site_root():
    """返回规范化的 SITE_ROOT，用于路径拼接，确保不以斜杠结尾（除非是空字符串）。"""
    root = config.REPO_SUBPATH
    if not root or root == '/':
        return ''
    return root.rstrip('/') # 移除尾部斜杠

def make_internal_url(path: str) -> str:
    """生成一个以 SITE_ROOT 为基础的规范化内部 URL，以 / 开头。"""
    site_root = get_site_root()
    
    # 移除输入 path 的头部斜杠
    path_without_leading_slash = path.lstrip('/')
    
    # 如果 site_root 是空字符串（即在根目录），则只返回 /path
    if not site_root:
        return f"/{path_without_leading_slash}"
    
    # 否则返回 /repo_subpath/path
    return f"{site_root}/{path_without_leading_slash}"

# NEW: 辅助函数 - 检查文章是否隐藏
def is_post_hidden(post: Dict[str, Any]) -> bool:
    """检查文章是否设置了 'hidden: true'"""
    # yaml.safe_load 会将 'true'/'True' 解析为 Python 的 True
    return post.get('hidden') in [True, 'true', 'True']

# --- 文件复制函数 (用于静态资源) ---

def copy_static_files():
    """复制 assets 目录到 _site 目录"""
    # 假设 assets 目录在项目根目录
    source_dir = 'assets'
    target_dir = os.path.join(config.BUILD_DIR, 'assets')
    
    if os.path.exists(source_dir):
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir) # 确保目标目录干净
        shutil.copytree(source_dir, target_dir)
        print(f"SUCCESS: Copied static files from {source_dir} to {target_dir}.")
    else:
        print(f"WARNING: Static assets directory '{source_dir}' not found.")

def copy_media_files():
    """复制 media 目录到 _site 目录 (如果存在)"""
    source_dir = config.MEDIA_DIR
    target_dir = os.path.join(config.BUILD_DIR, config.MEDIA_DIR)

    if os.path.exists(source_dir):
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        shutil.copytree(source_dir, target_dir)
        print(f"SUCCESS: Copied media files from {source_dir} to {target_dir}.")
    # 如果不存在，不打印警告，因为媒体目录可能是可选的


# --- 页面生成函数 ---

# NEW: 生成关于页面的函数
def generate_about_page(post: Dict[str, Any]):
    """
    生成 about.html 页面。
    post 字典必须包含 'title', 'content_html' 等元数据。
    """
    try:
        template = env.get_template('base.html')
        
        # 确保 link 字段存在，用于 canonical_url
        link = post.get('link', f"/{config.ABOUT_OUTPUT_FILE}")
        
        # 组装 JSON-LD Schema (可选，这里简化为 None)
        json_ld_schema = None 
        
        html_content = template.render(
            page_id='about',
            page_title=post.get('title', '关于我'), # 默认标题
            # 通用变量
            blog_title=config.BLOG_TITLE,
            blog_description=config.BLOG_DESCRIPTION,
            blog_author=config.BLOG_AUTHOR,
            site_root=make_internal_url(''),
            canonical_url=config.BASE_URL.rstrip('/') + link, # 明确使用完整 URL
            css_filename=config.CSS_FILENAME,
            current_year=datetime.now(timezone.utc).year,
            footer_time_info=f"最后构建于 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}.",
            json_ld_schema=json_ld_schema,

            # 页面特定变量
            content_html=post['content_html'],
            toc_html=post.get('toc_html'),
            # about 页面不显示文章列表
            posts=[], 
            max_posts_on_index=0, 
            post=post, 
            lang='zh-CN',
        )

        output_path = os.path.join(config.BUILD_DIR, config.ABOUT_OUTPUT_FILE)
        
        # 确保目录存在 (虽然 about.html 在根目录，但最好保留)
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"SUCCESS: Generated special page {config.ABOUT_OUTPUT_FILE}.")
    
    except Exception as e:
        print(f"Error generating about page: {type(e).__name__}: {e}")

# 生成单篇文章的 HTML 页面
def generate_post_html(post: Dict[str, Any]):
    """为单篇文章生成 HTML 页面"""
    try:
        template = env.get_template('base.html')
        
        # 组装 JSON-LD Schema (Article Schema)
        json_ld_schema = json.dumps({
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": post['title'],
            "description": post.get('excerpt', config.BLOG_DESCRIPTION),
            "datePublished": post['date'].isoformat(),
            "author": {
                "@type": "Person",
                "name": config.BLOG_AUTHOR
            },
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": config.BASE_URL.rstrip('/') + make_internal_url(post['link'])
            }
        }, ensure_ascii=False)
        
        html_content = template.render(
            page_id='post',
            page_title=post['title'],
            # 通用变量
            blog_title=config.BLOG_TITLE,
            blog_description=post.get('excerpt', config.BLOG_DESCRIPTION),
            blog_author=config.BLOG_AUTHOR,
            site_root=make_internal_url(''),
            canonical_url=config.BASE_URL.rstrip('/') + make_internal_url(post['link']),
            css_filename=config.CSS_FILENAME,
            current_year=datetime.now(timezone.utc).year,
            footer_time_info=f"最后构建于 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}.",
            json_ld_schema=json_ld_schema,
            
            # 页面特定变量
            content_html=post['content_html'],
            toc_html=post.get('toc_html'),
            post=post,
            lang='zh-CN',
        )

        # 确保输出路径存在
        output_path = os.path.join(config.BUILD_DIR, post['link'].lstrip('/'))
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated post: {post['link']}")

    except Exception as e:
        print(f"Error generating post '{post.get('title', 'Unknown')}' HTML: {type(e).__name__}: {e}")


# MODIFIED: generate_index_html (首页只显示可见文章)
def generate_index_html(all_posts: List[Dict[str, Any]]):
    """生成首页 index.html"""
    try:
        # 过滤掉被隐藏的文章
        visible_posts = [p for p in all_posts if not is_post_hidden(p)] 
        
        # 选取首页文章
        posts_for_index = visible_posts[:config.MAX_POSTS_ON_INDEX] 
        
        template = env.get_template('base.html')
        
        html_content = template.render(
            page_id='index',
            page_title=config.BLOG_TITLE,
            # 通用变量
            blog_title=config.BLOG_TITLE,
            blog_description=config.BLOG_DESCRIPTION,
            blog_author=config.BLOG_AUTHOR,
            site_root=make_internal_url(''),
            canonical_url=config.BASE_URL.rstrip('/') + make_internal_url('/'),
            css_filename=config.CSS_FILENAME,
            current_year=datetime.now(timezone.utc).year,
            footer_time_info=f"最后构建于 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}.",
            json_ld_schema=None, # 首页不使用 Article Schema
            
            # 列表特定变量
            posts=posts_for_index,
            max_posts_on_index=config.MAX_POSTS_ON_INDEX,
            content_html="", # 首页通过 posts 渲染列表
            lang='zh-CN',
        )

        output_path = os.path.join(config.BUILD_DIR, config.INDEX_FILE)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated {config.INDEX_FILE}.")
    
    except Exception as e:
        print(f"Error generating index.html: {type(e).__name__}: {e}")


# MODIFIED: generate_archive_html (归档页只显示可见文章)
def generate_archive_html(all_posts: List[Dict[str, Any]]):
    """生成归档页 archive.html (显示所有可见文章)"""
    try:
        # 过滤掉被隐藏的文章
        visible_posts = [p for p in all_posts if not is_post_hidden(p)]

        template = env.get_template('base.html')
        
        # 将文章按年份分组
        archive_map = defaultdict(list)
        for post in visible_posts:
            year = post['date'].year
            archive_map[year].append(post)
            
        # 按年份降序排序
        sorted_archive = sorted(archive_map.items(), key=lambda x: x[0], reverse=True)
            
        # 渲染归档页内容 (手动构建 content_html)
        content_html = "<h1>文章归档</h1>\n"
        for year, posts in sorted_archive:
            content_html += f"<h2>{year} ({len(posts)} 篇)</h2>\n<ul>\n"
            # 确保帖子在该年份内按日期降序排列
            sorted_posts = sorted(posts, key=lambda p: p['date'], reverse=True)
            for post in sorted_posts:
                link = make_internal_url(post['link'])
                date_str = post['date'].strftime('%Y-%m-%d')
                content_html += f"  <li><span class=\"archive-date\">{date_str}</span> - <a href=\"{link}\">{post['title']}</a></li>\n"
            content_html += "</ul>\n"
            
        html_content = template.render(
            page_id='archive',
            page_title='文章归档',
            # 通用变量
            blog_title=config.BLOG_TITLE,
            blog_description=config.BLOG_DESCRIPTION,
            blog_author=config.BLOG_AUTHOR,
            site_root=make_internal_url(''),
            canonical_url=config.BASE_URL.rstrip('/') + make_internal_url(config.ARCHIVE_FILE),
            css_filename=config.CSS_FILENAME,
            current_year=datetime.now(timezone.utc).year,
            footer_time_info=f"最后构建于 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}.",
            json_ld_schema=None,
            
            # 列表特定变量
            content_html=content_html, # 归档页通过 content_html 渲染列表
            posts=[], 
            max_posts_on_index=0,
            lang='zh-CN',
        )

        output_path = os.path.join(config.BUILD_DIR, config.ARCHIVE_FILE)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated {config.ARCHIVE_FILE}.")

    except Exception as e:
        print(f"Error generating archive.html: {type(e).__name__}: {e}")


# MODIFIED: generate_tags_list_html (标签列表页只统计可见文章)
def generate_tags_list_html(tag_map: Dict[str, List[Dict[str, Any]]]):
    """生成所有标签的列表页 tags.html"""
    try:
        # 过滤 tag_map，只包含可见文章
        filtered_tag_map = defaultdict(list)
        for tag, posts in tag_map.items():
            visible_posts = [p for p in posts if not is_post_hidden(p)]
            if visible_posts:
                # 只保留包含可见文章的标签，并使用可见文章列表
                filtered_tag_map[tag].extend(visible_posts)

        template = env.get_template('base.html')
        
        # 生成标签列表的 HTML (手动构建 content_html)
        content_html = "<h1>所有标签</h1>\n"
        content_html += "<ul>\n"
        # 按文章数量降序排列标签
        sorted_tags = sorted(filtered_tag_map.items(), key=lambda item: len(item[1]), reverse=True)
        
        for tag, posts in sorted_tags:
            tag_slug = tag_to_slug(tag)
            tag_link = make_internal_url(os.path.join(config.TAGS_DIR, f'{tag_slug}.html'))
            content_html += f"  <li><a href=\"{tag_link}\">{tag}</a> ({len(posts)} 篇)</li>\n"
        content_html += "</ul>\n"
        
        html_content = template.render(
            page_id='tags',
            page_title='所有标签',
            # 通用变量
            blog_title=config.BLOG_TITLE,
            blog_description=config.BLOG_DESCRIPTION,
            blog_author=config.BLOG_AUTHOR,
            site_root=make_internal_url(''),
            canonical_url=config.BASE_URL.rstrip('/') + make_internal_url(config.TAGS_LIST_FILE),
            css_filename=config.CSS_FILENAME,
            current_year=datetime.now(timezone.utc).year,
            footer_time_info=f"最后构建于 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}.",
            json_ld_schema=None,
            
            # 列表特定变量
            content_html=content_html, # 标签列表页通过 content_html 渲染列表
            posts=[], 
            max_posts_on_index=0,
            lang='zh-CN',
        )

        output_path = os.path.join(config.BUILD_DIR, config.TAGS_LIST_FILE)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated {config.TAGS_LIST_FILE}.")

    except Exception as e:
        print(f"Error generating tags.html: {type(e).__name__}: {e}")


# FIXED: generate_tag_page (现在将列表赋值给 posts，并假设 base.html 已修改以渲染 tag 页面的 posts 变量)
def generate_tag_page(tag: str, all_tag_posts: List[Dict[str, Any]]):
    """为单个标签生成页面"""
    try:
        # 1. 过滤掉被隐藏的文章
        visible_tag_posts = [p for p in all_tag_posts if not is_post_hidden(p)]
        
        if not visible_tag_posts:
            # 如果所有文章都被隐藏，则不生成该标签页
            print(f"INFO: Skipping tag '{tag}' page generation as all posts are hidden.")
            return
            
        template = env.get_template('base.html')
        tag_slug = tag_to_slug(tag)
        output_filename = f'{tag_slug}.html'
        
        # 2. 渲染模板
        # 关键修复：将列表传递给 posts 变量，并假设 base.html 会像首页一样渲染它。
        # 这样可以利用 base.html 中复杂的列表项渲染逻辑。
        html_content = template.render(
            page_id='tag', # <--- 确保 page_id 是 'tag'
            page_title=f"标签: {tag}",
            # 通用变量
            blog_title=config.BLOG_TITLE,
            blog_description=config.BLOG_DESCRIPTION,
            blog_author=config.BLOG_AUTHOR,
            site_root=make_internal_url(''),
            canonical_url=config.BASE_URL.rstrip('/') + make_internal_url(os.path.join(config.TAGS_DIR, output_filename)),
            css_filename=config.CSS_FILENAME,
            current_year=datetime.now(timezone.utc).year,
            footer_time_info=f"最后构建于 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}.",
            json_ld_schema=None,
            
            # 列表特定变量
            tag=tag,
            posts=visible_tag_posts, # <--- 关键：传递可见文章列表
            max_posts_on_index=len(visible_tag_posts) + 1, # 确保全部显示
            content_html="", # <--- 关键：content_html 置空，让模板使用 posts 渲染
            lang='zh-CN',
        )

        output_path = os.path.join(config.TAGS_OUTPUT_DIR, output_filename)
        
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"SUCCESS: Generated tag page: {output_filename}.")

    except Exception as e:
        print(f"Error generating tag page for '{tag}': {type(e).__name__}: {e}")


# --- XML/RSS 生成函数 ---

def generate_robots_txt():
    """生成 robots.txt"""
    content = f"""User-agent: *
Allow: /
Sitemap: {config.BASE_URL.rstrip('/')}{make_internal_url(config.SITEMAP_FILE)}
"""
    try:
        output_path = os.path.join(config.BUILD_DIR, 'robots.txt')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("SUCCESS: Generated robots.txt.")
    except Exception as e:
        print(f"Error generating robots.txt: {e}")

# MODIFIED: generate_sitemap (Sitemap只包含可见文章和页面)
def generate_sitemap(parsed_posts: List[Dict[str, Any]]) -> str:
    """
    生成 sitemap.xml。
    传入的 parsed_posts 应该已经是过滤后的可见文章和特殊页面列表。
    """
    base_url_normalized = config.BASE_URL.rstrip('/')
    
    urls = []
    
    # 首页
    urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url('/')}</loc>
        <changefreq>daily</changefreq>
        <priority>1.0</priority>
    </url>""")
    
    # 归档页
    urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url(config.ARCHIVE_FILE)}</loc>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>
    </url>""")

    # 标签列表页
    urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url(config.TAGS_LIST_FILE)}</loc>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>
    </url>""")

    # 文章和特殊页面
    for post in parsed_posts:
        # NOTE: 链接可能已经是 /about.html 或 /posts/slug.html
        link = make_internal_url(post.get('link', '/')) 
        
        # 确保日期存在并格式化
        lastmod_date = post.get('date', datetime.now(timezone.utc)).strftime('%Y-%m-%d')
        
        urls.append(f"""
    <url>
        <loc>{base_url_normalized}{link}</loc>
        <lastmod>{lastmod_date}</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.6</priority>
    </url>""")
        
    sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{''.join(urls)}
</urlset>"""
    return sitemap_content

# MODIFIED: generate_rss (RSS只包含可见文章)
def generate_rss(parsed_posts: List[Dict[str, Any]]) -> str:
    """
    生成 RSS feed。
    传入的 parsed_posts 应该已经是过滤后的可见文章列表。
    """
    
    items = []
    base_url_normalized = config.BASE_URL.rstrip('/')
    
    # 仅取最新的10篇可见文章
    for post in parsed_posts[:10]:
        # 使用 get 安全获取 link
        post_link = post.get('link')
        if not post_link:
            continue # 如果没有 link，跳过 RSS 条目
            
        # 修复文章链接
        link = f"{base_url_normalized}{make_internal_url(post_link)}"
        pub_date = post['date'].strftime('%a, %d %b %Y %H:%M:%S +0000') # RFC 822 格式
        
        # 使用 CDATA 包装 content_html
        items.append(f"""
    <item>
      <title>{post['title']}</title>
      <link>{link}</link>
      <pubDate>{pub_date}</pubDate>
      <guid isPermaLink="true">{link}</guid>
      <description><![CDATA[{post['content_html']}]]></description>
    </item>""")
    
    rss_file_url = make_internal_url(config.RSS_FILE)
    index_url = make_internal_url('/')
    
    rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
    <title>{config.BLOG_TITLE}</title>
    <link>{base_url_normalized}{index_url}</link>
    <atom:link href="{base_url_normalized}{rss_file_url}" rel="self" type="application/rss+xml" />
    <description>{config.BLOG_DESCRIPTION}</description>
    <language>zh-cn</language>
    <lastBuildDate>{datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>
{''.join(items)}
</channel>
</rss>"""
    return rss_content
