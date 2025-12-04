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
    # 确保该函数与 parser.py 中的定义一致
    return tag_name.lower().replace(' ', '-')

def get_site_root():
    """返回规范化的 SITE_ROOT，用于路径拼接，确保不以斜杠结尾（除非是空字符串）。"""
    root = config.REPO_SUBPATH or config.SITE_ROOT
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

# 辅助函数 - 检查文章是否隐藏
def is_post_hidden(post: Dict[str, Any]) -> bool:
    """检查文章是否设置了 'hidden: true'"""
    return post.get('hidden') in [True, 'true', 'True']

# --- 文件复制函数 (保持不变) ---

def copy_static_files():
    """复制 assets 目录到 _site 目录"""
    source_dir = 'assets'
    target_dir = os.path.join(config.BUILD_DIR, 'assets')
    
    if os.path.exists(source_dir):
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir) 
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


# --- 页面生成函数 ---

# generate_about_page (保持不变)
def generate_about_page(post: Dict[str, Any]):
    """生成 about.html 页面。"""
    try:
        template = env.get_template('base.html')
        link = post.get('link', f"/{config.ABOUT_OUTPUT_FILE}")
        json_ld_schema = None 
        content_with_title = f"<h1>{post.get('title', '关于我')}</h1>\n{post['content_html']}"
        
        html_content = template.render(
            page_id='about',
            page_title=post.get('title', '关于我'), 
            # 通用变量
            blog_title=config.BLOG_TITLE,
            blog_description=config.BLOG_DESCRIPTION,
            blog_author=config.BLOG_AUTHOR,
            site_root=make_internal_url(''),
            canonical_url=config.BASE_URL.rstrip('/') + link, 
            css_filename=config.CSS_FILENAME,
            current_year=datetime.now(timezone.utc).year,
            footer_time_info=f"最后构建于 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}.",
            json_ld_schema=json_ld_schema,

            # 页面特定变量
            content_html=content_with_title,
            toc_html=post.get('toc_html'),
            posts=[], 
            max_posts_on_index=0, 
            post=post, 
            lang='zh-CN',
            post_date=None, 
            post_tags=[],
        )

        output_path = os.path.join(config.BUILD_DIR, config.ABOUT_OUTPUT_FILE)
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"SUCCESS: Generated special page {config.ABOUT_OUTPUT_FILE}.")
    
    except Exception as e:
        print(f"Error generating about page: {type(e).__name__}: {e}")

# generate_post_html (保持不变)
def generate_post_html(post: Dict[str, Any]):
    """为单篇文章生成 HTML 页面"""
    try:
        template = env.get_template('base.html')
        
        # JSON-LD Schema
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
        
        post_tags_data = post.get('tags', []) 
        
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
            post_date=post['date'].strftime('%Y-%m-%d'),
            post_tags=post_tags_data,
            posts=[],
        )

        output_path = os.path.join(config.BUILD_DIR, post['link'].lstrip('/'))
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated post: {post['link']}")

    except Exception as e:
        print(f"Error generating post '{post.get('title', 'Unknown')}' HTML: {type(e).__name__}: {e}")


# generate_index_html (保持不变)
def generate_index_html(all_posts: List[Dict[str, Any]]):
    """生成首页 index.html"""
    try:
        visible_posts = [p for p in all_posts if not is_post_hidden(p)] 
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
            json_ld_schema=None, 
            
            # 列表特定变量 (通过 posts 渲染富列表)
            posts=posts_for_index,
            max_posts_on_index=config.MAX_POSTS_ON_INDEX,
            content_html="", 
            lang='zh-CN',
        )

        output_path = os.path.join(config.BUILD_DIR, config.INDEX_FILE)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated {config.INDEX_FILE}.")
    
    except Exception as e:
        print(f"Error generating index.html: {type(e).__name__}: {e}")


# generate_archive_html (保持不变)
def generate_archive_html(all_posts: List[Dict[str, Any]]):
    """生成归档页 archive.html (显示所有可见文章)"""
    try:
        visible_posts = [p for p in all_posts if not is_post_hidden(p)]
        template = env.get_template('base.html')
        
        archive_map = defaultdict(list)
        for post in visible_posts:
            year = post['date'].year
            archive_map[year].append(post)
            
        sorted_archive = sorted(archive_map.items(), key=lambda x: x[0], reverse=True)
            
        # 渲染归档页内容 (手动构建 content_html，包含 h1 标题)
        content_html = "<h1>文章归档</h1>\n"
        for year, posts in sorted_archive:
            content_html += f"<h2>{year} ({len(posts)} 篇)</h2>\n<ul class=\"archive-list\">\n"
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
            
            # 列表特定变量 (通过 content_html 渲染简洁列表)
            content_html=content_html,
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


# generate_tags_list_html (保持不变)
def generate_tags_list_html(tag_map: Dict[str, List[Dict[str, Any]]]):
    """生成所有标签的列表页 tags.html"""
    try:
        filtered_tag_map = defaultdict(list)
        for tag, posts in tag_map.items():
            visible_posts = [p for p in posts if not is_post_hidden(p)]
            if visible_posts:
                filtered_tag_map[tag].extend(visible_posts)

        template = env.get_template('base.html')
        
        # 生成标签列表的 HTML (手动构建 content_html，包含 h1 标题)
        content_html = "<h1>所有标签</h1>\n"
        content_html += "<ul class=\"tags-cloud-list\">\n"
        sorted_tags = sorted(filtered_tag_map.items(), key=lambda item: len(item[1]), reverse=True)
        
        for tag, posts in sorted_tags:
            tag_slug = tag_to_slug(tag)
            tag_link = make_internal_url(os.path.join(config.TAGS_DIR, f'{tag_slug}.html'))
            content_html += f"  <li><a href=\"{tag_link}\" class=\"tag-cloud-item\">{tag}</a> ({len(posts)} 篇)</li>\n"
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
            
            # 列表特定变量 (通过 content_html 渲染简洁列表)
            content_html=content_html,
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


# 关键修复函数：generate_tag_page
def generate_tag_page(tag: str, all_tag_posts: List[Dict[str, Any]]):
    """为单个标签生成页面"""
    try:
        # 1. 过滤掉被隐藏的文章
        visible_tag_posts = [p for p in all_tag_posts if not is_post_hidden(p)]
        
        # ！！！关键调试点 1：检查此处打印的文章数量是否 > 0 
        print(f"DEBUG: Tag '{tag}' has {len(visible_tag_posts)} visible posts.")
        
        if not visible_tag_posts:
            # 如果所有文章都被隐藏或列表为空，则不生成该标签页
            print(f"INFO: Skipping tag '{tag}' page generation as all posts are hidden/empty.")
            return 
            
        template = env.get_template('base.html')
        tag_slug = tag_to_slug(tag)
        output_filename = f'{tag_slug}.html'
        
        # 2. 渲染模板
        html_content = template.render(
            page_id='tag', # <--- 必须是 'tag'
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
            posts=visible_tag_posts, # <--- 关键：文章列表必须传入 posts 变量
            max_posts_on_index=len(visible_tag_posts) + 1, 
            content_html="", # content_html 置空，让模板使用 posts 渲染
            lang='zh-CN',
        )

        output_path = os.path.join(config.TAGS_OUTPUT_DIR, output_filename)
        
        # 冗余检查：确保目录存在（防止 autobuild.py 失败）
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # ！！！关键调试点 2：检查输出路径是否正确
        print(f"SUCCESS: Generated tag page: {output_path} (URL: tags/{output_filename}).")

    except Exception as e:
        print(f"Error generating tag page for '{tag}': {type(e).__name__}: {e}")


# --- XML/RSS 生成函数 (保持不变) ---
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

# generate_sitemap (保持不变)
def generate_sitemap(parsed_posts: List[Dict[str, Any]]) -> str:
    """生成 sitemap.xml。"""
    # ... (代码省略) ...
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
        link = make_internal_url(post.get('link', '/')) 
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

# generate_rss (保持不变)
def generate_rss(parsed_posts: List[Dict[str, Any]]) -> str:
    """生成 RSS feed。"""
    # ... (代码省略) ...
    items = []
    base_url_normalized = config.BASE_URL.rstrip('/')
    
    # 仅取最新的10篇可见文章
    for post in parsed_posts[:10]:
        post_link = post.get('link')
        if not post_link:
            continue
            
        link = f"{base_url_normalized}{make_internal_url(post_link)}"
        pub_date = post['date'].strftime('%a, %d %b %Y %H:%M:%S +0000') 
        
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
