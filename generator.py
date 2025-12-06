# generator.py (核心链接修复和标签链接清洗版)

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
    生成规范化的内部 URL。
    强制转换为 '目录模式' (Pretty URL): /slug/
    """
    if not path:
        return ""
        
    normalized_path = path if path.startswith('/') else f'/{path}'
    site_root = get_site_root_prefix()
    
    # 1. 忽略大小写移除 .html 后缀
    # ⚠️ 特殊处理：RSS 文件和 404 文件保留后缀
    if normalized_path.lower().endswith('.html') and not normalized_path.lower().endswith(config.RSS_FILE) and not normalized_path.lower() == '/404.html':
        normalized_path = normalized_path[:-5]
    
    # 2. 确保路径末尾添加斜杠 (除了根目录和特殊文件)
    if normalized_path.lower() == '/index': 
        normalized_path = '/'
    elif normalized_path.lower() == '/404' or normalized_path.lower() == '/404.html':
        pass 
    elif normalized_path.lower().endswith(config.RSS_FILE):
        pass
    elif normalized_path != '/' and not normalized_path.endswith('/'):
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

# --- [关键修复] 数据清洗函数 ---

def process_posts_for_template(posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    深度清洗文章列表。
    复制 post 对象，并将其中的 'link' 属性强制转换为 Pretty URL。
    同时，为所有标签添加一个已清洗的 'link' 属性。
    """
    cleaned_posts = []
    for post in posts:
        new_post = post.copy()
        
        # 清洗主链接
        if 'link' in new_post:
            new_post['link'] = make_internal_url(new_post['link'])
            
        # 清洗导航链接 (上一篇/下一篇)
        if 'prev_post_nav' in new_post and new_post['prev_post_nav']:
            nav = new_post['prev_post_nav'].copy()
            nav['link'] = make_internal_url(nav['link'])
            new_post['prev_post_nav'] = nav
            
        if 'next_post_nav' in new_post and new_post['next_post_nav']:
            nav = new_post['next_post_nav'].copy()
            nav['link'] = make_internal_url(nav['link'])
            new_post['next_post_nav'] = nav
            
        # ！！！新增关键修复：清洗标签链接！！！
        if 'tags' in new_post and new_post['tags']:
            cleaned_tags = []
            for tag in new_post['tags']:
                tag_copy = tag.copy()
                # 构造标签的路径
                tag_path = f"{config.TAGS_DIR_NAME}/{tag_copy['slug']}"
                # 使用 make_internal_url 清洗，生成 /tags/slug/ 格式的完整链接
                tag_copy['link'] = make_internal_url(tag_path) 
                cleaned_tags.append(tag_copy)
            new_post['tags'] = cleaned_tags
            
        cleaned_posts.append(new_post)
    return cleaned_posts

# --- 核心生成函数 ---

def generate_post_page(post: Dict[str, Any]):
    """生成单篇文章页面 (输出为 slug/index.html)"""
    try:
        relative_link = post.get('link')
        if not relative_link:
            return

        # [文件输出路径] 强制转换为 directory/index.html 结构
        if relative_link.lower() == '404.html':
            return
        else:
            clean_name = relative_link[:-5] if relative_link.lower().endswith('.html') else relative_link
            clean_name = clean_name.strip('/')
            output_dir = os.path.join(config.BUILD_DIR, clean_name)
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, 'index.html')
            page_id_override = 'post'

        template = env.get_template('base.html')
        
        # 准备数据：清洗当前文章的导航链接和标签链接
        processed_list = process_posts_for_template([post])
        current_post_processed = processed_list[0]

        context = {
            'page_id': page_id_override,
            'page_title': post['title'],
            'blog_title': config.BLOG_TITLE,
            'blog_description': post.get('excerpt', config.BLOG_DESCRIPTION),
            'blog_author': config.BLOG_AUTHOR,
            'content_html': post['content_html'],
            'post': current_post_processed, # 使用清洗过链接的 post 对象
            'post_date': post.get('date_formatted', ''),
            'post_tags': current_post_processed.get('tags', []), # ！！！使用清洗过 link 的标签列表！！！
            'toc_html': post.get('toc_html'),
            'prev_post_nav': current_post_processed.get('prev_post_nav'),
            'next_post_nav': current_post_processed.get('next_post_nav'),
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{make_internal_url(relative_link)}",
            'footer_time_info': post.get('footer_time_info', ''),
        }

        html_content = template.render(context)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Generated: {output_path}")

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
            'posts': process_posts_for_template(visible_posts), # 关键：传入清洗后的文章列表 (包含清洗后的 tag.link)
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
        print("Generated: index.html")
    except Exception as e:
        print(f"Error index.html: {e}")


def generate_archive_html(sorted_posts: List[Dict[str, Any]], build_time_info: str):
    """生成归档页 (archive/index.html)"""
    try:
        # 输出路径：archive/index.html
        output_dir = os.path.join(config.BUILD_DIR, 'archive')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'index.html')
        
        visible_posts = [p for p in sorted_posts if not is_post_hidden(p)]
        
        archive_by_year = defaultdict(list)
        # 注意：这里不对 post 进行 process_posts_for_template，因为只在内部生成 HTML
        # 只需要确保 post['link'] 是干净的。
        for post in visible_posts:
            archive_by_year[post['date'].year].append(post)
        
        sorted_archive = sorted(archive_by_year.items(), key=lambda item: item[0], reverse=True)

        template = env.get_template('base.html')
        
        archive_html = "<h1>文章归档</h1>\n"
        for year, posts in sorted_archive:
            archive_html += f"<h2>{year} ({len(posts)} 篇)</h2>\n<ul>\n"
            for post in posts:
                # 关键：这里直接调用 make_internal_url 生成纯净链接
                link = make_internal_url(post['link']) 
                archive_html += f"<li><a href=\"{link}\">{post['title']}</a> - {post['date_formatted']}</li>\n"
            archive_html += "</ul>\n"
            
        context = {
            'page_id': 'archive',
            'page_title': '文章归档',
            'blog_title': config.BLOG_TITLE,
            'blog_description': '归档',
            'blog_author': config.BLOG_AUTHOR,
            'content_html': archive_html, 
            'posts': [],
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{make_internal_url('/archive')}",
            'footer_time_info': build_time_info,
        }
        
        html_content = template.render(context)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print("Generated: archive/index.html")
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
            # 生成链接: /tags/slug/
            link = make_internal_url(f"{config.TAGS_DIR_NAME}/{tag_slug}")
            count = len(posts)
            font_size = max(1.0, min(2.5, 0.8 + count * 0.15))
            tags_html += f"<a href=\"{link}\" style=\"font-size: {font_size}rem;\" class=\"tag-cloud-item\">{tag} ({count})</a>\n"
        tags_html += "</div>\n"

        template = env.get_template('base.html')
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
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{make_internal_url('/tags')}",
            'footer_time_info': build_time_info,
        }
        
        html_content = template.render(context)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print("Generated: tags/index.html")
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
        
        # 关键：清洗列表，确保 post 中的 tag 链接也被清洗
        processed_posts = process_posts_for_template(sorted_tag_posts)
        
        context = {
            'page_id': 'tag',
            'page_title': f"标签: {tag_name}",
            'blog_title': config.BLOG_TITLE,
            'blog_description': config.BLOG_DESCRIPTION,
            'blog_author': config.BLOG_AUTHOR,
            'posts': processed_posts, 
            'tag': tag_name, 
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{make_internal_url(f'{config.TAGS_DIR_NAME}/{tag_slug}')}",
            'footer_time_info': build_time_info,
        }
        
        html_content = template.render(context)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Generated tag page: {tag_name}")
    except Exception as e:
        print(f"Error tag page {tag_name}: {e}")

# --- 辅助生成：Robots, Sitemap, RSS (确保使用 make_internal_url 清洗路径) ---

def generate_robots_txt():
    """生成 robots.txt"""
    try:
        output_path = os.path.join(config.BUILD_DIR, 'robots.txt')
        content = f"User-agent: *\nAllow: /\nSitemap: {config.BASE_URL.rstrip('/')}{make_internal_url(config.SITEMAP_FILE)}\n"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Generated: robots.txt")
    except Exception as e:
        print(f"Error robots.txt: {e}")

def generate_sitemap(parsed_posts: List[Dict[str, Any]]) -> str:
    """生成 sitemap.xml"""
    urls = []
    base_url = config.BASE_URL.rstrip('/')
    
    # 静态页面
    for path, prio in [('/', '1.0'), ('/archive', '0.8'), ('/tags', '0.8'), ('/404', '0.1'), (config.RSS_FILE, '0.1')]:
        urls.append(f"<url><loc>{base_url}{make_internal_url(path)}</loc><priority>{prio}</priority></url>")

    if os.path.exists(os.path.join(config.BUILD_DIR, 'about', 'index.html')):
         urls.append(f"<url><loc>{base_url}{make_internal_url('/about')}</loc><priority>0.8</priority></url>")

    # 文章
    all_tags = set()
    for post in parsed_posts:
        if is_post_hidden(post) or not post.get('link'): continue
        
        link = f"{base_url}{make_internal_url(post['link'])}"
        lastmod = post['date'].strftime('%Y-%m-%d')
        urls.append(f"<url><loc>{link}</loc><lastmod>{lastmod}</lastmod><priority>0.6</priority></url>")
        
        for tag in post.get('tags', []):
            all_tags.add(tag['name'])
    
    # 标签
    for tag in all_tags:
        slug = tag_to_slug(tag)
        link = f"{base_url}{make_internal_url(f'{config.TAGS_DIR_NAME}/{slug}')}"
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
        # [文件输出路径] 强制转换为 directory/index.html 结构
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
        print(f"Generated: {page_id}/index.html")
    except Exception as e:
        print(f"Error {page_id}: {e}")
