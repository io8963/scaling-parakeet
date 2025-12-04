# generator.py

import os
import shutil 
import glob   
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Dict, Any, Tuple 
from jinja2 import Environment, FileSystemLoader
import json 
import config
# 关键修复：导入 parser 中的 tag_to_slug 函数，以确保使用一致的标签 URL 转换逻辑
from parser import tag_to_slug

# --- Jinja2 环境配置配置 ---
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=True,
    trim_blocks=True, 
    lstrip_blocks=True
)

# --- 辅助函数：路径和 URL (核心路径修正) ---

# 注意：为了确保一致性，这里使用 parser.py 中导入的 tag_to_slug 函数。
# 如果 parser.py 中没有定义，则使用这里默认的定义。
if 'tag_to_slug' not in locals():
    def tag_to_slug(tag_name: str) -> str:
        """将标签名转换为 URL 友好的 slug (小写，空格变'-')。"""
        # 如果 parser.py 中的 tag_to_slug 有特殊处理，这里应该从 parser 导入
        return tag_name.lower().replace(' ', '-')


def get_site_root_prefix() -> str:
    """
    获取网站在部署环境中的相对子目录路径前缀。
    如果 REPO_SUBPATH 为空，则返回空字符串 ''。
    如果 REPO_SUBPATH 为 '/blog'，则返回 '/blog'。
    """
    root = config.REPO_SUBPATH.strip()
    if not root or root == '/':
        return ''
    # 确保它不以 '/' 结尾，但以 '/' 开头 (例如 '/blog')
    root = root.rstrip('/')
    return root if root.startswith('/') else f'/{root}'

def make_internal_url(path: str) -> str:
    """
    生成一个以相对 SITE_ROOT 为基础的规范化内部 URL。
    结果格式为 /repo-subpath/path 或 /path。
    """
    # 确保路径以 / 开头
    normalized_path = path if path.startswith('/') else f'/{path}'
    site_root = get_site_root_prefix()
    
    # 如果 site_root 为空，直接返回 normalized_path (例如 /posts/a.html)
    if not site_root:
        return normalized_path
    
    # 否则，返回 /site_root/path (例如 /blog/posts/a.html)
    return f"{site_root}{normalized_path}"

def is_post_hidden(post: Dict[str, Any]) -> bool:
    """检查文章是否应被隐藏（例如 status: draft）"""
    return post.get('status', 'published').lower() == 'draft'

# --- 核心生成函数 ---

def generate_post_page(post: Dict[str, Any]):
    """生成单篇文章页面"""
    try:
        # 获取文章的 link 路径 (e.g., /posts/2023-12-01-hello-world.html)
        relative_link = post.get('link')
        if not relative_link:
            print(f"ERROR: Post {post.get('title', post.get('filename'))} has no link defined.")
            return

        # 目标文件路径
        output_path = os.path.join(config.BUILD_DIR, relative_link.lstrip('/'))
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 准备模板数据
        template = env.get_template('base.html')
        
        # 准备 JSON-LD Schema (如果需要)
        # ... (此处省略 JSON-LD 逻辑，因为它不在本次修改范围内)
        
        # 准备上下文
        context = {
            'page_id': 'post',
            'page_title': post['title'],
            'blog_title': config.BLOG_TITLE,
            'blog_description': post.get('excerpt', config.BLOG_DESCRIPTION),
            'blog_author': config.BLOG_AUTHOR,
            'content_html': post['content_html'],
            'post': post,
            'post_date': post['date_formatted'],
            'post_tags': post.get('tags', []),
            'toc_html': post.get('toc_html'),
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{make_internal_url(relative_link)}",
            'footer_time_info': f"Build time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        }

        html_content = template.render(context)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated post page for '{post['title']}' at {relative_link}")

    except Exception as e:
        print(f"Error generating post page for {post.get('title')}: {type(e).__name__}: {e}")


def generate_index_html(sorted_posts: List[Dict[str, Any]]):
    """生成首页 (index.html)"""
    try:
        output_path = os.path.join(config.BUILD_DIR, 'index.html')
        
        # 筛选出要显示的帖子 (非草稿，且限制数量)
        visible_posts = [p for p in sorted_posts if not is_post_hidden(p)][:config.MAX_POSTS_ON_INDEX]

        template = env.get_template('base.html')
        context = {
            'page_id': 'index',
            'page_title': config.BLOG_TITLE,
            'blog_title': config.BLOG_TITLE,
            'blog_description': config.BLOG_DESCRIPTION,
            'blog_author': config.BLOG_AUTHOR,
            'posts': visible_posts,
            'max_posts_on_index': config.MAX_POSTS_ON_INDEX,
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{get_site_root_prefix()}/",
            'footer_time_info': f"Build time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        }
        
        html_content = template.render(context)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print("SUCCESS: Generated index.html.")

    except Exception as e:
        print(f"Error generating index.html: {type(e).__name__}: {e}")

def generate_archive_html(sorted_posts: List[Dict[str, Any]]):
    """生成归档页 (archive.html)"""
    try:
        output_path = os.path.join(config.BUILD_DIR, 'archive.html')
        
        visible_posts = [p for p in sorted_posts if not is_post_hidden(p)]
        
        # 按年份分组
        archive_by_year = defaultdict(list)
        for post in visible_posts:
            year = post['date'].year
            archive_by_year[year].append(post)
        
        # 按照年份降序排序
        sorted_archive = sorted(archive_by_year.items(), key=lambda item: item[0], reverse=True)

        template = env.get_template('base.html')
        
        # 准备内容 HTML
        archive_html = "<h1>文章归档</h1>\n"
        for year, posts in sorted_archive:
            archive_html += f"<h2>{year} ({len(posts)} 篇)</h2>\n<ul>\n"
            for post in posts:
                # 使用 make_internal_url 确保链接正确
                link = make_internal_url(post['link']) 
                archive_html += f"<li><a href=\"{link}\">{post['title']}</a> - {post['date_formatted']}</li>\n"
            archive_html += "</ul>\n"
            
        context = {
            'page_id': 'archive',
            'page_title': '文章归档',
            'blog_title': config.BLOG_TITLE,
            'blog_description': '所有文章的完整列表',
            'blog_author': config.BLOG_AUTHOR,
            'content_html': archive_html, # 将归档列表作为 content_html 注入
            'posts': visible_posts,
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{get_site_root_prefix()}/archive.html",
            'footer_time_info': f"Build time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        }
        
        html_content = template.render(context)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print("SUCCESS: Generated archive.html.")

    except Exception as e:
        print(f"Error generating archive.html: {type(e).__name__}: {e}")


def generate_tags_list_html(tag_map: Dict[str, List[Dict[str, Any]]]):
    """生成标签列表页 (tags.html)"""
    try:
        output_path = os.path.join(config.BUILD_DIR, 'tags.html')
        
        sorted_tags = sorted(tag_map.items(), key=lambda item: len(item[1]), reverse=True)

        # 准备内容 HTML
        tags_html = "<h1>标签列表</h1>\n"
        tags_html += "<div class=\"tag-cloud\">\n"
        
        for tag, posts in sorted_tags:
            # 使用 tag_to_slug 生成正确的链接
            tag_slug = tag_to_slug(tag)
            link = make_internal_url(f"{config.TAGS_DIR_NAME}/{tag_slug}.html")
            
            # 根据文章数量设置字体大小 (示例，可以自定义)
            count = len(posts)
            font_size = max(1.0, min(2.5, 0.8 + count * 0.15))
            
            tags_html += f"<a href=\"{link}\" style=\"font-size: {font_size}rem;\" class=\"tag-cloud-item\">{tag} ({count})</a>\n"
            
        tags_html += "</div>\n"

        template = env.get_template('base.html')
        context = {
            'page_id': 'tags',
            'page_title': '所有标签',
            'blog_title': config.BLOG_TITLE,
            'blog_description': '网站所有标签列表',
            'blog_author': config.BLOG_AUTHOR,
            'content_html': tags_html,
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{get_site_root_prefix()}/tags.html",
            'footer_time_info': f"Build time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        }
        
        html_content = template.render(context)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print("SUCCESS: Generated tags.html.")

    except Exception as e:
        print(f"Error generating tags.html: {type(e).__name__}: {e}")


def generate_tag_page(tag_name: str, sorted_tag_posts: List[Dict[str, Any]]):
    """
    MODIFIED: 生成单个标签页面 (e.g., /tags/python.html)。
    确保链接和路径设置正确。
    """
    try:
        # 1. 确保使用 URL 友好的 slug
        tag_slug = tag_to_slug(tag_name)
        
        # 2. 目标文件路径和目录
        filename = f"{tag_slug}.html"
        # 目标输出目录 (例如: _site/tags/)
        output_dir = os.path.join(config.BUILD_DIR, config.TAGS_DIR_NAME)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)

        # 3. 准备模板数据
        template = env.get_template('base.html')
        
        # 关键的上下文数据
        context = {
            'page_id': 'tag',
            # page_title 格式应为：标签: Python (共 5 篇)
            'page_title': f"标签: {tag_name} (共 {len(sorted_tag_posts)} 篇)",
            'blog_title': config.BLOG_TITLE,
            'blog_description': config.BLOG_DESCRIPTION,
            'blog_author': config.BLOG_AUTHOR,
            'posts': sorted_tag_posts, # 文章列表将由 base.html 模板渲染
            'tag': tag_name, # 当前标签名
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            # 构建规范 URL：确保 BASE_URL, SITE_ROOT, 和文件路径正确拼接
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{make_internal_url(f'{config.TAGS_DIR_NAME}/{filename}')}",
            'footer_time_info': f"Build time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        }
        
        html_content = template.render(context)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated tag page for '{tag_name}' at {os.path.join(config.TAGS_DIR_NAME, filename)}")
        
    except Exception as e:
        print(f"Error generating tag page for {tag_name}: {type(e).__name__}: {e}")

# ... (省略 generate_robots_txt, generate_sitemap, generate_rss 等函数，假设它们保持不变)
# 为了提供完整的可运行文件，我将包含所有标准辅助函数。

# --- 辅助生成：Robots, Sitemap, RSS ---

def generate_robots_txt():
    """生成 robots.txt"""
    try:
        output_path = os.path.join(config.BUILD_DIR, 'robots.txt')
        
        # 假设所有内容都允许索引，但指向 sitemap
        content = f"""User-agent: *
Allow: /
Sitemap: {config.BASE_URL.rstrip('/')}{make_internal_url(config.SITEMAP_FILE)}
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("SUCCESS: Generated robots.txt.")
        
    except Exception as e:
        print(f"Error generating robots.txt: {type(e).__name__}: {e}")


def generate_sitemap(parsed_posts: List[Dict[str, Any]]) -> str:
    """生成 sitemap.xml"""
    
    urls = []
    base_url_normalized = config.BASE_URL.rstrip('/')
    
    # 1. 首页
    urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url('/')}</loc>
        <priority>1.0</priority>
    </url>""")
    
    # 2. 归档页
    urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url('/archive.html')}</loc>
        <priority>0.8</priority>
    </url>""")
    
    # 3. 标签列表页
    urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url('/tags.html')}</loc>
        <priority>0.8</priority>
    </url>""")
    
    # 4. 关于页 (假设存在)
    if os.path.exists(os.path.join(config.MARKDOWN_DIR, config.ABOUT_PAGE)):
        urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url('/about.html')}</loc>
        <priority>0.8</priority>
    </url>""")

    # 5. 文章页面和标签页面
    all_tags = set()
    for post in parsed_posts:
        if is_post_hidden(post):
            continue
            
        post_link = post.get('link')
        if not post_link:
            continue
            
        link = f"{base_url_normalized}{make_internal_url(post_link)}"
        lastmod = post['date'].strftime('%Y-%m-%d')
        
        urls.append(f"""
    <url>
        <loc>{link}</loc>
        <lastmod>{lastmod}</lastmod>
        <priority>0.6</priority>
    </url>""")
        
        # 收集所有标签，以便生成标签页面的 sitemap 条目
        if post.get('tags'):
            for tag in post['tags']:
                all_tags.add(tag['name'])
    
    # 6. 标签页
    for tag in all_tags:
        tag_slug = tag_to_slug(tag)
        tag_link = f"{config.TAGS_DIR_NAME}/{tag_slug}.html"
        link = f"{base_url_normalized}{make_internal_url(tag_link)}"
        urls.append(f"""
    <url>
        <loc>{link}</loc>
        <priority>0.5</priority>
    </url>""")


    sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    {"".join(urls)}
</urlset>"""

    return sitemap_content


def generate_rss(parsed_posts: List[Dict[str, Any]]) -> str:
    """生成 RSS Feed (rss.xml)"""
    
    items = []
    base_url_normalized = config.BASE_URL.rstrip('/')
    
    # 仅取最新的10篇
    visible_posts = [p for p in parsed_posts if not is_post_hidden(p)]
    
    for post in visible_posts[:10]:
        post_link = post.get('link')
        if not post_link:
            continue
            
        link = f"{base_url_normalized}{make_internal_url(post_link)}"
        # RFC 822 格式, 必须是 UTC 时间
        pub_date = datetime.combine(post['date'], datetime.min.time(), tzinfo=timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000') 
        
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
    <description>{config.BLOG_DESCRIPTION}</description>
    <language>zh-cn</language>
    <atom:link href="{base_url_normalized}{rss_file_url}" rel="self" type="application/rss+xml" />
    <lastBuildDate>{datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>
    {"".join(items)}
</channel>
</rss>"""

    return rss_content


def generate_page_html(content_html: str, page_title: str, page_id: str, canonical_path: str):
    """生成通用页面 (如 about.html)"""
    try:
        output_path = os.path.join(config.BUILD_DIR, f'{page_id}.html')
        
        template = env.get_template('base.html')
        context = {
            'page_id': page_id,
            'page_title': page_title,
            'blog_title': config.BLOG_TITLE,
            'blog_description': config.BLOG_DESCRIPTION,
            'blog_author': config.BLOG_AUTHOR,
            'content_html': content_html, 
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{make_internal_url(canonical_path)}",
            'footer_time_info': f"Build time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        }
        
        html_content = template.render(context)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated {page_id}.html.")

    except Exception as e:
        print(f"Error generating {page_id}.html: {type(e).__name__}: {e}")
