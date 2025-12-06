# generator.py (核心链接修复和标签链接清洗版 + JSON-LD)

import os
import shutil 
import glob   
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional 
from jinja2 import Environment, FileSystemLoader
import json 
import re 
import config
from parser import tag_to_slug 
from bs4 import BeautifulSoup # 引入 BeautifulSoup

# --- Jinja2 环境配置配置 ---
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=True,
    trim_blocks=True, 
    lstrip_blocks=True
)

# --- 辅助函数：路径和 URL (核心路径修正) ---

def get_site_root_prefix() -> str:
    """获取网站在部署环境中的相对子目录路径前缀。"""
    root = config.REPO_SUBPATH.strip()
    # 确保 config.SITE_ROOT 始终是 REPO_SUBPATH 的规范化版本
    if not root or root == '/':
        # 如果是根路径部署，则返回空字符串
        config.SITE_ROOT = '' 
        return ''
    root = root.rstrip('/')
    config.SITE_ROOT = root if root.startswith('/') else f'/{root}'
    return config.SITE_ROOT

def make_internal_url(path: str) -> str:
    """
    生成规范化的内部 URL。
    强制转换为 '目录模式' (Pretty URL): /slug/
    """
    if not path:
        return ""
        
    # 1. 确保以 / 开头
    if not path.startswith('/'):
        path = '/' + path

    # 2. 移除 .html
    if path.endswith('.html'):
        path = path[:-5]
        
    # 3. 规范化为 /slug/ 结构
    if not path.endswith('/'):
        path += '/'
        
    # 4. 移除多余的斜杠，但不影响根路径 /
    path = re.sub(r'/+', '/', path)
    return path


def generate_post_page(post: Dict[str, Any]):
    """生成单篇文章页面 (posts/slug/index.html)"""
    # ... (代码保持不变)
    post_slug_dir = os.path.join(config.BUILD_DIR, config.POSTS_DIR_NAME, post['slug'])
    os.makedirs(post_slug_dir, exist_ok=True)
    output_path = os.path.join(post_slug_dir, 'index.html')

    template = env.get_template('base.html')
    
    # 获取导航链接
    prev_post_nav = None
    next_post_nav = None
    if 'prev_post' in post:
        prev_post_nav = {
            'title': post['prev_post']['title'],
            'link': make_internal_url(f"{config.POSTS_DIR_NAME}/{post['prev_post']['slug']}")
        }
    if 'next_post' in post:
        next_post_nav = {
            'title': post['next_post']['title'],
            'link': make_internal_url(f"{config.POSTS_DIR_NAME}/{post['next_post']['slug']}")
        }
        
    # JSON-LD Schema
    json_ld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post['title'],
        "datePublished": post['date'].isoformat(),
        "dateModified": post['last_modified'].isoformat() if post.get('last_modified') else post['date'].isoformat(),
        "author": {
            "@type": "Person",
            "name": config.BLOG_AUTHOR
        },
        "description": post['summary'],
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": f"{config.BASE_URL.rstrip('/')}{make_internal_url(f'{config.POSTS_DIR_NAME}/{post['slug']}')}"
        }
        # 更多属性可以根据需要添加，如 image, publisher 等
    }
    
    context = {
        'page_id': 'post',
        'page_title': post['title'],
        'blog_title': config.BLOG_TITLE,
        'blog_description': config.BLOG_DESCRIPTION,
        'blog_author': config.BLOG_AUTHOR,
        'post': post,
        'content_html': post['content_html'], 
        'toc_html': post['toc_html'],
        'site_root': get_site_root_prefix(),
        'current_year': datetime.now().year,
        'css_filename': config.CSS_FILENAME,
        'canonical_url': f"{config.BASE_URL.rstrip('/')}{make_internal_url(f'{config.POSTS_DIR_NAME}/{post['slug']}')}",
        'prev_post_nav': prev_post_nav,
        'next_post_nav': next_post_nav,
        'footer_time_info': post['build_time_info'],
        'json_ld_schema': json.dumps(json_ld, ensure_ascii=False, indent=4)
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(template.render(context))
        
    print(f"  -> Generated: {config.POSTS_DIR_NAME}/{post['slug']}/")


def generate_index_html(posts: List[Dict[str, Any]], build_time_info: str):
    """生成首页 (index.html)"""
    output_path = os.path.join(config.BUILD_DIR, 'index.html')
    template = env.get_template('base.html')
    
    # JSON-LD Schema (Website)
    json_ld = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": config.BLOG_TITLE,
        "url": config.BASE_URL.rstrip('/') + make_internal_url('/'),
        "description": config.BLOG_DESCRIPTION,
    }

    context = {
        'page_id': 'index',
        'page_title': '首页',
        'blog_title': config.BLOG_TITLE,
        'blog_description': config.BLOG_DESCRIPTION,
        'blog_author': config.BLOG_AUTHOR,
        'posts': posts, # 首页直接传入 posts 列表，在 base.html 中循环渲染
        'content_html': '', # 首页内容直接在 base.html 中渲染，这里为空
        'site_root': get_site_root_prefix(),
        'current_year': datetime.now().year,
        'css_filename': config.CSS_FILENAME,
        'canonical_url': f"{config.BASE_URL.rstrip('/')}{make_internal_url('/')}",
        'footer_time_info': build_time_info,
        'json_ld_schema': json.dumps(json_ld, ensure_ascii=False, indent=4)
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(template.render(context))
        
    print("  -> Generated: /index.html")


def generate_archive_html(posts: List[Dict[str, Any]], build_time_info: str):
    """生成归档页面 (archive/index.html)"""
    
    # 1. 按年份分组
    archive_groups = defaultdict(list)
    for post in posts:
        year = post['date'].year
        archive_groups[year].append(post)

    # 2. 生成归档列表 HTML 字符串
    html_parts = []
    # 按年份倒序排列
    for year in sorted(archive_groups.keys(), reverse=True):
        html_parts.append(f'<h2>{year}</h2>')
        # 使用新的归档列表类名，方便 CSS 调整
        html_parts.append('<ul class="archive-list">')
        for post in archive_groups[year]:
            # 归档页只显示日期和标题
            # 格式：<a href="/post/slug/">[日期] 标题</a>
            post_link = make_internal_url(f"{config.POSTS_DIR_NAME}/{post['slug']}")
            # 使用 list-item-archive 类名，方便 CSS 调整
            html_parts.append(f'<li><a href="{post_link}" class="list-item-archive"><span class="archive-date">{post['date_formatted']}</span><span class="archive-title">{post['title']}</span></a></li>')
        html_parts.append('</ul>')
    
    content_html = '\n'.join(html_parts)
    
    # 3. 调用通用页面生成函数
    generate_page_html(
        content_html=content_html, 
        page_title='文章归档', 
        page_id='archive', 
        canonical_path_with_html='archive/index.html',
        build_time_info=build_time_info
    )


def generate_tags_list_html(tag_map: Dict[str, List[Dict[str, Any]]], build_time_info: str):
    """
    [FIXED] 生成标签列表页面 (tags-list/index.html)
    该函数现在生成标签列表的 HTML 并传递给通用生成器。
    """
    # 1. 生成标签列表 HTML 字符串
    html_parts = []
    # 按标签名排序
    sorted_tags = sorted(tag_map.keys())
    
    # 使用新的标签列表类名，方便 CSS 调整
    html_parts.append('<div class="tags-list-container">')
    for tag in sorted_tags:
        count = len(tag_map[tag])
        tag_link = make_internal_url(f"{config.TAGS_DIR_NAME}/{tag_to_slug(tag)}")
        
        # 使用 tag-entry 类名，方便 CSS 调整。同时显示文章数量。
        html_parts.append(f'<a href="{tag_link}" class="tag-entry"><span class="tag-name">{tag}</span><span class="tag-count">({count})</span></a>')

    html_parts.append('</div>')
    
    content_html = '\n'.join(html_parts)
    
    # 2. 调用通用页面生成函数
    generate_page_html(
        content_html=content_html, 
        page_title='所有标签', 
        page_id='tags-list', 
        canonical_path_with_html='tags/index.html',
        build_time_info=build_time_info
    )


def generate_tag_page(tag: str, posts: List[Dict[str, Any]], build_time_info: str):
    """生成单个标签页面 (tags/slug/index.html)"""
    tag_slug = tag_to_slug(tag)
    output_dir = os.path.join(config.BUILD_DIR, config.TAGS_DIR_NAME, tag_slug)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'index.html')

    # 生成文章列表 HTML 
    html_parts = []
    # 使用新的归档列表类名
    html_parts.append('<ul class="archive-list">')
    for post in posts:
        post_link = make_internal_url(f"{config.POSTS_DIR_NAME}/{post['slug']}")
        # 使用 list-item-archive 类名
        html_parts.append(f'<li><a href="{post_link}" class="list-item-archive"><span class="archive-date">{post['date_formatted']}</span><span class="archive-title">{post['title']}</span></a></li>')
    html_parts.append('</ul>')
    content_html = '\n'.join(html_parts)
    
    # 调用通用页面生成函数
    generate_page_html(
        content_html=content_html, 
        page_title=f"标签：{tag}", 
        page_id='tag', 
        canonical_path_with_html=f'tags/{tag_slug}/index.html',
        build_time_info=build_time_info
    )


def generate_about_html(build_time_info: str):
    """生成关于页面 (about/index.html)"""
    # ... (代码保持不变)
    try:
        about_path = os.path.join(config.CONTENT_DIR, 'about.md')
        if not os.path.exists(about_path):
            print("Warning: 'about.md' not found. Skipping 'About' page generation.")
            return

        with open(about_path, 'r', encoding='utf-8') as f:
            metadata, content_html, toc_html = parser.get_metadata_and_content(f.read())
        
        # 调用通用页面生成函数
        generate_page_html(
            content_html=content_html, 
            page_title='关于', 
            page_id='about', 
            canonical_path_with_html='about/index.html',
            build_time_info=build_time_info
        )
        print("  -> Generated: /about/")

    except Exception as e:
        print(f"Error generating about page: {e}")
        
    
def generate_page_html(content_html: str, page_title: str, page_id: str, canonical_path_with_html: str, build_time_info: str):
    """生成通用页面 (输出为 page_id/index.html)"""
    try:
        # [文件输出路径] 强制转换为 directory/index.html 结构
        output_dir = os.path.join(config.BUILD_DIR, page_id)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'index.html')
        
        template = env.get_template('base.html')
        canonical_path = make_internal_url(canonical_path_with_html) 
        
        # 默认 JSON-LD (WebPage)
        json_ld = {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": page_title,
            "url": f"{config.BASE_URL.rstrip('/')}{canonical_path}",
        }
        
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
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{canonical_path}",
            'footer_time_info': build_time_info,
            'json_ld_schema': json.dumps(json_ld, ensure_ascii=False, indent=4)
        }
        
        # 针对 'tags-list' 和 'archive' 页面特殊处理，防止在 base.html 中重复渲染
        if page_id == 'tags-list':
             # 标签列表页，内容通过 content_html 传入
             pass
        elif page_id == 'archive':
             # 归档页，内容通过 content_html 传入
             pass

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(template.render(context))
        
        print(f"  -> Generated: /{page_id}/")

    except Exception as e:
        print(f"Error generating page '{page_id}': {e}")
        
        
def generate_sitemap(posts: List[Dict[str, Any]]) -> str:
    # ... (代码保持不变)
    items = []
    # 首页
    items.append(f'<url><loc>{config.BASE_URL.rstrip('/')}{make_internal_url('/')}</loc><lastmod>{datetime.now(timezone.utc).isoformat()}</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url>')
    
    # 归档、标签列表、关于页
    for page in ['archive', 'tags', 'about']:
         items.append(f'<url><loc>{config.BASE_URL.rstrip('/')}{make_internal_url(f'/{page}/')}</loc><lastmod>{datetime.now(timezone.utc).isoformat()}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>')
         
    # 文章页
    for post in posts:
        post_url = make_internal_url(f'{config.POSTS_DIR_NAME}/{post['slug']}')
        last_modified = post['last_modified'] if post.get('last_modified') else post['date']
        # 确保 last_modified 是带有 timezone 信息的 datetime 对象
        if isinstance(last_modified, datetime):
             last_modified_utc = last_modified.astimezone(timezone.utc)
        elif isinstance(last_modified, date):
             last_modified_utc = datetime.combine(last_modified, time.min, tzinfo=timezone.utc)
        else:
             last_modified_utc = datetime.now(timezone.utc) # Fallback
             
        items.append(f'<url><loc>{config.BASE_URL.rstrip('/')}{post_url}</loc><lastmod>{last_modified_utc.isoformat().split('.')[0]}Z</lastmod><changefreq>weekly</changefreq><priority>0.7</priority></url>')

    # 单个标签页 (仅获取 slug, 假设它们生成了)
    all_tags = set()
    for post in posts:
        for tag in post['tags']:
            all_tags.add(tag_to_slug(tag['name']))
            
    for tag_slug in all_tags:
        items.append(f'<url><loc>{config.BASE_URL.rstrip('/')}{make_internal_url(f'/{config.TAGS_DIR_NAME}/{tag_slug}/')}</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>')


    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{"".join(items)}</urlset>'


def generate_robots_txt() -> None:
    # ... (代码保持不变)
    robots_content = f"""
User-agent: *
Allow: /
Sitemap: {config.BASE_URL.rstrip('/')}/sitemap.xml
"""
    output_path = os.path.join(config.BUILD_DIR, 'robots.txt')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(robots_content.strip())
        
    print("  -> Generated: /robots.txt")

    
def generate_rss(posts: List[Dict[str, Any]]) -> str:
    # ... (代码保持不变)
    items = []
    # 只取最新的 15 篇
    for post in posts[:15]:
        post_url = f"{config.BASE_URL.rstrip('/')}{make_internal_url(f'{config.POSTS_DIR_NAME}/{post['slug']}')}"
        
        # 确保 pubDate 格式正确 (RFC-822)
        pub_date_gmt = post['date'].replace(tzinfo=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

        item = f"""
        <item>
            <title>{post['title']}</title>
            <link>{post_url}</link>
            <guid isPermaLink="true">{post_url}</guid>
            <pubDate>{pub_date_gmt}</pubDate>
            <author>{config.BLOG_AUTHOR}</author>
            <description><![CDATA[{post['content_html']}]]></description>
        </item>"""
        items.append(item.strip())

    # 确保 lastBuildDate 格式正确
    last_build_date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    return f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel><title>{config.BLOG_TITLE}</title><link>{config.BASE_URL.rstrip('/')}</link><description>{config.BLOG_DESCRIPTION}</description><language>zh-cn</language><atom:link href="{config.BASE_URL.rstrip('/')}/rss.xml" rel="self" type="application/rss+xml" /><lastBuildDate>{last_build_date}</lastBuildDate>{"".join(items)}</channel></rss>'
