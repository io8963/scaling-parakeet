# generator.py (完整内容，包含所有路径和链接的 Pretty URL 修复)

import os
import shutil 
import glob   
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional 
from jinja2 import Environment, FileSystemLoader
import json 
import config
from parser import tag_to_slug 

# --- Jinja2 环境配置配置 ---
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=True,
    trim_blocks=True, 
    lstrip_blocks=True
)

# --- 辅助函数：路径和 URL (核心路径修正：Directory-Style Pretty URL) ---

if 'tag_to_slug' not in locals():
    def tag_to_slug(tag_name: str) -> str:
        return tag_name.lower().replace(' ', '-')


def get_site_root_prefix() -> str:
    """
    获取网站在部署环境中的相对子目录路径前缀。
    """
    root = config.REPO_SUBPATH.strip()
    if not root or root == '/':
        return ''
    root = root.rstrip('/')
    return root if root.startswith('/') else f'/{root}'

def make_internal_url(path: str) -> str:
    """
    生成一个以相对 SITE_ROOT 为基础的规范化内部 URL。
    
    [FIX] 修改为生成带斜杠的 Pretty URL 模式，例如 /blog/archive/。
    """
    normalized_path = path if path.startswith('/') else f'/{path}'
    site_root = get_site_root_prefix()
    
    # 1. 移除 .html 后缀
    if normalized_path.endswith('.html'):
        normalized_path = normalized_path[:-5]
        
    # 2. 确保路径末尾添加斜杠 (Directory-style Pretty URL 模式)
    # 特殊处理：index 应该指向 /，404 不应该被链接
    if normalized_path.lower() == '/index': # /index.html -> /index
        normalized_path = '/'
    elif normalized_path.lower() == '/404':
        # 404.html 保留，因为它不是一个常规链接
        pass
    elif normalized_path != '/' and not normalized_path.endswith('/'):
        # e.g., /archive -> /archive/
        normalized_path = f'{normalized_path}/'
    
    # 3. 组合 site_root 和 normalized_path
    if not site_root:
        return normalized_path
    
    # 如果 normalized_path 是 '/'，则返回 site_root 本身
    if normalized_path == '/':
        return f"{site_root}/"
    
    # 否则，组合 site_root 和 path
    return f"{site_root}{normalized_path}"


def is_post_hidden(post: Dict[str, Any]) -> bool:
    """
    检查文章是否应被隐藏（例如 status: draft 或 hidden: true）。
    """
    return post.get('status', 'published').lower() == 'draft' or post.get('hidden') is True

# --- [新增] 辅助函数：修复文章列表和导航的链接 ---

def fix_post_links_for_template(post_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    更新文章列表中的 post['link'] 属性，使用 make_internal_url 转换为带斜杠的 Pretty URL。
    """
    fixed_posts = []
    for post in post_list:
        fixed_post = post.copy()
        original_link = fixed_post.get('link')
        if original_link:
            fixed_post['link'] = make_internal_url(original_link)
        fixed_posts.append(fixed_post)
    return fixed_posts

def fix_nav_post_link(nav_post: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    更新上一篇/下一篇文章导航对象中的 post['link'] 属性。
    """
    if nav_post:
        fixed_nav_post = nav_post.copy()
        original_link = fixed_nav_post.get('link')
        if original_link:
            fixed_nav_post['link'] = make_internal_url(original_link)
        return fixed_nav_post
    return None

# --- 核心生成函数 ---

def generate_post_page(post: Dict[str, Any]):
    """生成单篇文章页面"""
    try:
        relative_link = post.get('link')
        if not relative_link:
            print(f"ERROR: Post {post.get('title', post.get('filename'))} has no link defined.")
            return

        # [FIX] 输出路径：从 page.html 变为 page/index.html
        # 例如: '2024/hello-world.html' 变为 '2024/hello-world/index.html'
        if relative_link.lower() == '404.html':
            output_path = os.path.join(config.BUILD_DIR, relative_link.lstrip('/'))
        else:
            relative_dir = relative_link.rstrip('/').replace('.html', '')
            output_dir = os.path.join(config.BUILD_DIR, relative_dir.lstrip('/'))
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, 'index.html')


        template = env.get_template('base.html')
        
        # 兼容性处理：如果 link 是 404.html，则 page_id 设为 404
        page_id_override = '404' if relative_link == '404.html' else 'post'
        
        # 生成用户可见的 URL 时使用 make_internal_url
        internal_url_link = make_internal_url(relative_link)

        context = {
            'page_id': page_id_override,
            'page_title': post['title'],
            'blog_title': config.BLOG_TITLE,
            'blog_description': post.get('excerpt', config.BLOG_DESCRIPTION),
            'blog_author': config.BLOG_AUTHOR,
            'content_html': post['content_html'],
            'post': post,
            'post_date': post.get('date_formatted', ''),
            'post_tags': post.get('tags', []),
            'toc_html': post.get('toc_html'),
            # [FIX] 修复文章导航链接
            'prev_post_nav': fix_nav_post_link(post.get('prev_post_nav')),
            'next_post_nav': fix_nav_post_link(post.get('next_post_nav')),
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{internal_url_link}",
            'footer_time_info': post.get('footer_time_info', f"网站构建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"),
        }

        html_content = template.render(context)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated post page for '{post['title']}' at {output_path}")

    except Exception as e:
        print(f"Error generating post page for {post.get('title')}: {type(e).__name__}: {e}")


def generate_index_html(sorted_posts: List[Dict[str, Any]], build_time_info: str):
    """生成首页 (index.html)"""
    try:
        # 首页保持 index.html 文件名不变
        output_path = os.path.join(config.BUILD_DIR, 'index.html')
        
        # 首页只显示未隐藏的文章
        visible_posts = [p for p in sorted_posts if not is_post_hidden(p)][:config.MAX_POSTS_ON_INDEX]

        template = env.get_template('base.html')
        context = {
            'page_id': 'index',
            'page_title': config.BLOG_TITLE,
            'blog_title': config.BLOG_TITLE,
            'blog_description': config.BLOG_DESCRIPTION,
            'blog_author': config.BLOG_AUTHOR,
            # [FIX] 修复文章列表中的链接
            'posts': fix_post_links_for_template(visible_posts),
            'max_posts_on_index': config.MAX_POSTS_ON_INDEX,
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{get_site_root_prefix()}/",
            'footer_time_info': build_time_info,
        }
        
        html_content = template.render(context)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print("SUCCESS: Generated index.html.")

    except Exception as e:
        print(f"Error generating index.html: {type(e).__name__}: {e}")


def generate_archive_html(sorted_posts: List[Dict[str, Any]], build_time_info: str):
    """生成归档页 (archive/index.html)"""
    try:
        # [FIX] 输出路径：从 archive.html 变为 archive/index.html
        output_dir = os.path.join(config.BUILD_DIR, 'archive')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'index.html')
        
        # 归档页只显示未隐藏的文章
        visible_posts = [p for p in sorted_posts if not is_post_hidden(p)]
        
        # 按年份分组
        archive_by_year = defaultdict(list)
        for post in visible_posts:
            year = post['date'].year
            archive_by_year[year].append(post)
        
        sorted_archive = sorted(archive_by_year.items(), key=lambda item: item[0], reverse=True)

        template = env.get_template('base.html')
        
        # 准备内容 HTML
        archive_html = "<h1>文章归档</h1>\n"
        for year, posts in sorted_archive:
            archive_html += f"<h2>{year} ({len(posts)} 篇)</h2>\n<ul>\n"
            for post in posts:
                # 这里的 link 必须使用 make_internal_url 修复
                link = make_internal_url(post['link']) 
                archive_html += f"<li><a href=\"{link}\">{post['title']}</a> - {post['date_formatted']}</li>\n"
            archive_html += "</ul>\n"
            
        # [MODIFIED] 使用 make_internal_url 生成带斜杠的规范链接
        canonical_path = make_internal_url('/archive.html')
            
        context = {
            'page_id': 'archive',
            'page_title': '文章归档',
            'blog_title': config.BLOG_TITLE,
            'blog_description': '所有文章的完整列表',
            'blog_author': config.BLOG_AUTHOR,
            'content_html': archive_html, 
            # [FIX] 修复文章列表中的链接 (即使 archive 页面没有直接循环 post 列表，也保持数据一致性)
            'posts': fix_post_links_for_template(visible_posts),
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{canonical_path}",
            'footer_time_info': build_time_info,
        }
        
        html_content = template.render(context)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated archive/index.html.")

    except Exception as e:
        print(f"Error generating archive.html: {type(e).__name__}: {e}")


def generate_tags_list_html(tag_map: Dict[str, List[Dict[str, Any]]], build_time_info: str):
    """生成标签列表页 (tags/index.html)"""
    try:
        # [FIX] 输出路径：从 tags.html 变为 tags/index.html
        output_dir = os.path.join(config.BUILD_DIR, 'tags')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'index.html')
        
        sorted_tags = sorted(tag_map.items(), key=lambda item: len(item[1]), reverse=True)

        # 准备内容 HTML
        tags_html = "<h1>标签列表</h1>\n"
        tags_html += "<div class=\"tag-cloud\">\n"
        
        for tag, posts in sorted_tags:
            tag_slug = tag_to_slug(tag)
            # [MODIFIED] make_internal_url 负责处理
            link = make_internal_url(f"{config.TAGS_DIR_NAME}/{tag_slug}.html")
            
            count = len(posts)
            font_size = max(1.0, min(2.5, 0.8 + count * 0.15))
            
            tags_html += f"<a href=\"{link}\" style=\"font-size: {font_size}rem;\" class=\"tag-cloud-item\">{tag} ({count})</a>\n"
            
        tags_html += "</div>\n"

        template = env.get_template('base.html')
        
        # [MODIFIED] 使用 make_internal_url 生成带斜杠的规范链接
        canonical_path = make_internal_url('/tags.html')
        
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
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{canonical_path}",
            'footer_time_info': build_time_info,
        }
        
        html_content = template.render(context)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated tags/index.html.")

    except Exception as e:
        print(f"Error generating tags.html: {type(e).__name__}: {e}")


def generate_tag_page(tag_name: str, sorted_tag_posts: List[Dict[str, Any]], build_time_info: str):
    """生成单个标签页面 (e.g., /tags/python/index.html)。"""
    try:
        tag_slug = tag_to_slug(tag_name)
        
        # [FIX] 输出路径：从 tags/tag.html 变为 tags/tag/index.html
        filename_base = f"{tag_slug}"
        output_dir = os.path.join(config.BUILD_DIR, config.TAGS_DIR_NAME, filename_base)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'index.html')

        template = env.get_template('base.html')
        
        # 链接用于 make_internal_url
        link_with_html = f'{config.TAGS_DIR_NAME}/{tag_slug}.html'
        canonical_path = make_internal_url(link_with_html)
        
        context = {
            'page_id': 'tag',
            'page_title': f"标签: {tag_name} (共 {len(sorted_tag_posts)} 篇)",
            'blog_title': config.BLOG_TITLE,
            'blog_description': config.BLOG_DESCRIPTION,
            'blog_author': config.BLOG_AUTHOR,
            # [FIX] 修复文章列表中的链接
            'posts': fix_post_links_for_template(sorted_tag_posts), 
            'tag': tag_name, 
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{canonical_path}",
            'footer_time_info': build_time_info,
        }
        
        html_content = template.render(context)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated tag page for '{tag_name}' at {os.path.join(config.TAGS_DIR_NAME, filename_base, 'index.html')}")
        
    except Exception as e:
        print(f"Error generating tag page for {tag_name}: {type(e).__name__}: {e}")

# --- 辅助生成：Robots, Sitemap, RSS (不变，因为它们内部调用 make_internal_url) ---

def generate_robots_txt():
    """生成 robots.txt"""
    try:
        output_path = os.path.join(config.BUILD_DIR, 'robots.txt')
        
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
    """
    生成 sitemap.xml
    [MODIFIED] 使用 make_internal_url 生成带斜杠的链接
    """
    
    urls = []
    base_url_normalized = config.BASE_URL.rstrip('/')
    
    # 1. 首页
    urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url('/')}</loc>
        <priority>1.0</priority>
    </url>""")
    
    # 2. 归档页
    # 链接为 /archive/
    urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url('/archive.html')}</loc>
        <priority>0.8</priority>
    </url>""")
    
    # 3. 标签列表页
    # 链接为 /tags/
    urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url('/tags.html')}</loc>
        <priority>0.8</priority>
    </url>""")
    
    # 4. 关于页 (仅在文件存在时加入)
    # [FIX] 检查路径是否为 about/index.html
    if os.path.exists(os.path.join(config.BUILD_DIR, 'about', 'index.html')):
        # 链接为 /about/
        urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url('/about.html')}</loc>
        <priority>0.8</priority>
    </url>""")

    # 5. 文章页面和标签页面
    all_tags = set()
    for post in parsed_posts:
        # parsed_posts 理论上只包含非隐藏/非 404 的文章，但双重保险
        if is_post_hidden(post):
            continue
            
        post_link = post.get('link')
        if not post_link:
            continue
            
        # 链接为 /post-title/
        link = f"{base_url_normalized}{make_internal_url(post_link)}"
        lastmod = post['date'].strftime('%Y-%m-%d')
        
        urls.append(f"""
    <url>
        <loc>{link}</loc>
        <lastmod>{lastmod}</lastmod>
        <priority>0.6</priority>
    </url>""")
        
        if post.get('tags'):
            for tag in post['tags']:
                all_tags.add(tag['name'])
    
    # 6. 标签页
    for tag in all_tags:
        tag_slug = tag_to_slug(tag)
        tag_link_with_html = f"{config.TAGS_DIR_NAME}/{tag_slug}.html"
        # 链接为 /tags/tag-name/
        link = f"{base_url_normalized}{make_internal_url(tag_link_with_html)}"
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
    
    # 确保只包含未隐藏的文章
    visible_posts = [p for p in parsed_posts if not is_post_hidden(p)]
    
    for post in visible_posts[:10]:
        post_link = post.get('link')
        if not post_link:
            continue
            
        # 链接为 /post-title/
        link = f"{base_url_normalized}{make_internal_url(post_link)}"
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


def generate_page_html(content_html: str, page_title: str, page_id: str, canonical_path_with_html: str, build_time_info: str):
    """生成通用页面 (如 about/index.html)"""
    try:
        # [FIX] 输出路径：从 page_id.html 变为 page_id/index.html
        output_dir = os.path.join(config.BUILD_DIR, page_id)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'index.html')
        
        template = env.get_template('base.html')
        
        # 链接为 /about/
        canonical_path = make_internal_url(canonical_path_with_html)
        
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
        }
        
        html_content = template.render(context)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated {page_id}/index.html.")

    except Exception as e:
        print(f"Error generating {page_id}.html: {type(e).__name__}: {e}")
