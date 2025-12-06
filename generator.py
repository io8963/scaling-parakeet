# generator.py (修复：强制 Directory-Style URL 和忽略大小写的后缀清理)

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

# --- 辅助函数：路径和 URL (核心路径修正) ---

if 'tag_to_slug' not in locals():
    def tag_to_slug(tag_name: str) -> str:
        return tag_name.lower().replace(' ', '-')

def get_site_root_prefix() -> str:
    """获取网站在部署环境中的相对子目录路径前缀。"""
    root = config.REPO_SUBPATH.strip()
    if not root or root == '/':
        return ''
    root = root.rstrip('/')
    return root if root.startswith('/') else f'/{root}'

def make_internal_url(path: str) -> str:
    """
    生成一个以相对 SITE_ROOT 为基础的规范化内部 URL。
    强制转换为 '目录模式' (Pretty URL)，即结尾带斜杠，无 .html 后缀。
    """
    if not path:
        return ""
        
    normalized_path = path if path.startswith('/') else f'/{path}'
    site_root = get_site_root_prefix()
    
    # [FIX] 1. 忽略大小写移除 .html 后缀
    if normalized_path.lower().endswith('.html'):
        normalized_path = normalized_path[:-5]
        
    # [FIX] 2. 确保路径末尾添加斜杠 (除了根目录)
    # 特殊处理：index -> /
    if normalized_path.lower() == '/index': 
        normalized_path = '/'
    elif normalized_path.lower() == '/404':
        # 404 保留原样（通常不作为链接跳转）
        pass
    elif normalized_path != '/' and not normalized_path.endswith('/'):
        # e.g., /archive -> /archive/
        normalized_path = f'{normalized_path}/'
    
    # 3. 组合 site_root 和 normalized_path
    if not site_root:
        return normalized_path
    
    if normalized_path == '/':
        return f"{site_root}/"
    
    return f"{site_root}{normalized_path}"

def is_post_hidden(post: Dict[str, Any]) -> bool:
    """检查文章是否应被隐藏。"""
    return post.get('status', 'published').lower() == 'draft' or post.get('hidden') is True

# --- [FIX] 数据预处理函数：批量修复列表中的链接 ---

def fix_post_links_for_template(post_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    复制文章列表并更新其中的 'link' 属性为 Pretty URL。
    确保模板中渲染的 {{ post.link }} 不包含 .html。
    """
    fixed_posts = []
    for post in post_list:
        # 创建副本以免修改原始数据影响其他逻辑
        fixed_post = post.copy()
        original_link = fixed_post.get('link')
        if original_link:
            # 转换为 /slug/ 格式
            fixed_post['link'] = make_internal_url(original_link)
        fixed_posts.append(fixed_post)
    return fixed_posts

def fix_nav_post_link(nav_post: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """修复上一篇/下一篇导航对象的链接。"""
    if nav_post:
        fixed_nav_post = nav_post.copy()
        original_link = fixed_nav_post.get('link')
        if original_link:
            fixed_nav_post['link'] = make_internal_url(original_link)
        return fixed_nav_post
    return None

# --- 核心生成函数 ---

def generate_post_page(post: Dict[str, Any]):
    """生成单篇文章页面 (输出为 slug/index.html)"""
    try:
        relative_link = post.get('link')
        if not relative_link:
            return

        # [FIX] 计算输出路径：确保生成 directory/index.html 结构
        # 无论原始 link 是 "aaa.html" 还是 "aaa.HTML"，都转为 "aaa/index.html"
        if relative_link.lower() == '404.html':
            output_path = os.path.join(config.BUILD_DIR, relative_link.lstrip('/'))
        else:
            # 移除扩展名，作为目录名
            if relative_link.lower().endswith('.html'):
                relative_dir = relative_link[:-5]
            else:
                relative_dir = relative_link
                
            relative_dir = relative_dir.strip('/')
            output_dir = os.path.join(config.BUILD_DIR, relative_dir)
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, 'index.html')

        template = env.get_template('base.html')
        page_id_override = '404' if relative_link == '404.html' else 'post'
        
        # 生成规范链接 (Pretty URL)
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
            # [FIX] 修复上下篇导航链接
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
            
        print(f"SUCCESS: Generated post at {output_path}")

    except Exception as e:
        print(f"Error generating post {post.get('title')}: {e}")


def generate_index_html(sorted_posts: List[Dict[str, Any]], build_time_info: str):
    """生成首页 (index.html)"""
    try:
        output_path = os.path.join(config.BUILD_DIR, 'index.html')
        visible_posts = [p for p in sorted_posts if not is_post_hidden(p)][:config.MAX_POSTS_ON_INDEX]

        template = env.get_template('base.html')
        context = {
            'page_id': 'index',
            'page_title': config.BLOG_TITLE,
            'blog_title': config.BLOG_TITLE,
            'blog_description': config.BLOG_DESCRIPTION,
            'blog_author': config.BLOG_AUTHOR,
            # [FIX] 传递修复过链接的文章列表
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
        print(f"Error index.html: {e}")


def generate_archive_html(sorted_posts: List[Dict[str, Any]], build_time_info: str):
    """生成归档页 (archive/index.html)"""
    try:
        # 输出为 archive/index.html
        output_dir = os.path.join(config.BUILD_DIR, 'archive')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'index.html')
        
        visible_posts = [p for p in sorted_posts if not is_post_hidden(p)]
        archive_by_year = defaultdict(list)
        for post in visible_posts:
            archive_by_year[post['date'].year].append(post)
        
        sorted_archive = sorted(archive_by_year.items(), key=lambda item: item[0], reverse=True)
        template = env.get_template('base.html')
        
        # 手动构建 HTML 时也使用 make_internal_url
        archive_html = "<h1>文章归档</h1>\n"
        for year, posts in sorted_archive:
            archive_html += f"<h2>{year} ({len(posts)} 篇)</h2>\n<ul>\n"
            for post in posts:
                link = make_internal_url(post['link']) 
                archive_html += f"<li><a href=\"{link}\">{post['title']}</a> - {post['date_formatted']}</li>\n"
            archive_html += "</ul>\n"
            
        canonical_path = make_internal_url('/archive.html')
            
        context = {
            'page_id': 'archive',
            'page_title': '文章归档',
            'blog_title': config.BLOG_TITLE,
            'blog_description': '归档',
            'blog_author': config.BLOG_AUTHOR,
            'content_html': archive_html, 
            # 传递修复后的列表以防模板需要遍历
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
        print(f"Error archive.html: {e}")


def generate_tags_list_html(tag_map: Dict[str, List[Dict[str, Any]]], build_time_info: str):
    """生成标签列表页 (tags/index.html)"""
    try:
        output_dir = os.path.join(config.BUILD_DIR, 'tags')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'index.html')
        
        sorted_tags = sorted(tag_map.items(), key=lambda item: len(item[1]), reverse=True)
        tags_html = "<h1>标签列表</h1>\n<div class=\"tag-cloud\">\n"
        
        for tag, posts in sorted_tags:
            tag_slug = tag_to_slug(tag)
            # 标签链接也必须是 Pretty URL
            link = make_internal_url(f"{config.TAGS_DIR_NAME}/{tag_slug}.html")
            count = len(posts)
            font_size = max(1.0, min(2.5, 0.8 + count * 0.15))
            tags_html += f"<a href=\"{link}\" style=\"font-size: {font_size}rem;\" class=\"tag-cloud-item\">{tag} ({count})</a>\n"
        tags_html += "</div>\n"

        template = env.get_template('base.html')
        canonical_path = make_internal_url('/tags.html')
        
        context = {
            'page_id': 'tags',
            'page_title': '所有标签',
            'blog_title': config.BLOG_TITLE,
            'blog_description': '标签',
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
        print(f"Error tags.html: {e}")


def generate_tag_page(tag_name: str, sorted_tag_posts: List[Dict[str, Any]], build_time_info: str):
    """生成单个标签页面 (tags/slug/index.html)"""
    try:
        tag_slug = tag_to_slug(tag_name)
        output_dir = os.path.join(config.BUILD_DIR, config.TAGS_DIR_NAME, tag_slug)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'index.html')

        template = env.get_template('base.html')
        link_with_html = f'{config.TAGS_DIR_NAME}/{tag_slug}.html'
        canonical_path = make_internal_url(link_with_html)
        
        context = {
            'page_id': 'tag',
            'page_title': f"标签: {tag_name}",
            'blog_title': config.BLOG_TITLE,
            'blog_description': config.BLOG_DESCRIPTION,
            'blog_author': config.BLOG_AUTHOR,
            # [FIX] 传递修复链接后的文章列表
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
        print(f"SUCCESS: Generated tag page for {tag_name}")
    except Exception as e:
        print(f"Error tag page {tag_name}: {e}")

# --- 辅助生成：Robots, Sitemap, RSS ---

def generate_robots_txt():
    """生成 robots.txt"""
    try:
        output_path = os.path.join(config.BUILD_DIR, 'robots.txt')
        content = f"User-agent: *\nAllow: /\nSitemap: {config.BASE_URL.rstrip('/')}{make_internal_url(config.SITEMAP_FILE)}\n"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("SUCCESS: Generated robots.txt.")
    except Exception as e:
        print(f"Error robots.txt: {e}")


def generate_sitemap(parsed_posts: List[Dict[str, Any]]) -> str:
    """生成 sitemap.xml (使用 Pretty URLs)"""
    urls = []
    base_url = config.BASE_URL.rstrip('/')
    
    # 静态页面
    for path, prio in [('/', '1.0'), ('/archive.html', '0.8'), ('/tags.html', '0.8')]:
        urls.append(f"<url><loc>{base_url}{make_internal_url(path)}</loc><priority>{prio}</priority></url>")
    
    if os.path.exists(os.path.join(config.BUILD_DIR, 'about', 'index.html')):
         urls.append(f"<url><loc>{base_url}{make_internal_url('/about.html')}</loc><priority>0.8</priority></url>")

    # 文章和标签
    all_tags = set()
    for post in parsed_posts:
        if is_post_hidden(post) or not post.get('link'): continue
        
        link = f"{base_url}{make_internal_url(post['link'])}"
        lastmod = post['date'].strftime('%Y-%m-%d')
        urls.append(f"<url><loc>{link}</loc><lastmod>{lastmod}</lastmod><priority>0.6</priority></url>")
        
        for tag in post.get('tags', []):
            all_tags.add(tag['name'])
    
    for tag in all_tags:
        slug = tag_to_slug(tag)
        link = f"{base_url}{make_internal_url(f'{config.TAGS_DIR_NAME}/{slug}.html')}"
        urls.append(f"<url><loc>{link}</loc><priority>0.5</priority></url>")

    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{"".join(urls)}</urlset>'


def generate_rss(parsed_posts: List[Dict[str, Any]]) -> str:
    """生成 RSS Feed"""
    items = []
    base_url = config.BASE_URL.rstrip('/')
    visible_posts = [p for p in parsed_posts if not is_post_hidden(p)]
    
    for post in visible_posts[:10]:
        if not post.get('link'): continue
        link = f"{base_url}{make_internal_url(post['link'])}"
        pub_date = datetime.combine(post['date'], datetime.min.time(), tzinfo=timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000') 
        items.append(f"<item><title>{post['title']}</title><link>{link}</link><pubDate>{pub_date}</pubDate><guid isPermaLink=\"true\">{link}</guid><description><![CDATA[{post['content_html']}]]></description></item>")
    
    rss_link = make_internal_url(config.RSS_FILE)
    return f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel><title>{config.BLOG_TITLE}</title><link>{base_url}{make_internal_url("/")}</link><description>{config.BLOG_DESCRIPTION}</description><language>zh-cn</language><atom:link href="{base_url}{rss_link}" rel="self" type="application/rss+xml" /><lastBuildDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>{"".join(items)}</channel></rss>'


def generate_page_html(content_html: str, page_title: str, page_id: str, canonical_path_with_html: str, build_time_info: str):
    """生成通用页面 (输出为 page_id/index.html)"""
    try:
        output_dir = os.path.join(config.BUILD_DIR, page_id)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'index.html')
        
        template = env.get_template('base.html')
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
        print(f"SUCCESS: Generated {page_id}/index.html")
    except Exception as e:
        print(f"Error {page_id}: {e}")
