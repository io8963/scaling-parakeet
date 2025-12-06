# generator.py (核心链接修复和标签链接清洗版 + JSON-LD)

import os
import shutil 
import glob   
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional 
from jinja2 import Environment, FileSystemLoader
import json 
import re # 引入 re 用于 JSON-LD 中的图片提取
import config
from parser import tag_to_slug 

# 导入 HTML 最小化工具
try:
    import minify_html
except ImportError:
    print("Warning: minify-html library not found. HTML output will not be minified.")
    minify_html = None


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
    将相对路径（如 posts/slug.html）转换为带 SITE_ROOT 前缀的 URL。
    同时将 posts/slug.html 转换为 posts/slug/ 形式 (Pretty URL)
    """
    get_site_root_prefix() # 确保 config.SITE_ROOT 已被计算
    
    if path.startswith('/'):
        # 对于根路径链接 (如 /archive/)
        return f"{config.SITE_ROOT}{path}"
    
    # 转换为 Pretty URL 结构 (posts/slug.html -> posts/slug/)
    if path.endswith('.html'):
        path_without_ext = path[:-5] # 移除 .html
        # 确保只对 posts/ 下的链接进行转换，例如 posts/slug -> posts/slug/
        if path_without_ext.startswith(f"{config.POSTS_DIR_NAME}/"):
             # path_without_ext = path_without_ext.replace(f"{config.POSTS_DIR_NAME}/", f"{config.POSTS_DIR_NAME}/") # 保持 posts/ 前缀
             path = path_without_ext + '/' # 加上尾部斜杠
        else:
             # 对于非 posts 目录下的 html 文件（如 page.html），不使用 Pretty URL
             path = path
             

    # 规范化：替换多余的 //
    return f"{config.SITE_ROOT}/{path}".replace('//', '/')


# --- 辅助函数：HTML 最小化 ---
def minify_html_output(html_content: str) -> str:
    """如果安装了 minify_html，则对内容进行最小化处理。"""
    if minify_html:
        try:
            # ⭐ 核心修复：移除不兼容的参数 'do_not_minify_doctype'
            return minify_html.minify(
                html_content,
                keep_comments=False,
                keep_html_and_head_opening_tags=True,
                keep_spaces_between_attributes=False,
                minify_css=True,
                minify_js=True,
                remove_processing_instructions=True,
            )
        except TypeError as e:
            # 如果 minify-html 版本太老，不支持某些参数，则打印警告并返回原始内容
            print(f"Warning: HTML Minify failed due to library version issue ({e}). Skipping minify for this page.")
            return html_content
        except Exception as e:
            print(f"Error during HTML Minify: {e}. Skipping minify.")
            return html_content
    return html_content

# --- 辅助函数：JSON-LD Schema ---

def generate_post_schema(post: Dict[str, Any]) -> str:
    """生成文章页面的 Article Schema JSON-LD"""
    # post['link'] 是 posts/slug.html 格式，make_internal_url 将其转为 /posts/slug/ 格式
    canonical_url = f"{config.BASE_URL.rstrip('/')}{make_internal_url(post['link'])}"
    
    # 尝试从内容中提取第一张图片作为 schema 的图片
    image_match = re.search(r'<img.*?src=["\'](.*?)["\'].*?>', post['content_html'])
    image_url = image_match.group(1) if image_match else None
    
    # 如果图片是相对路径，尝试将其转换为绝对路径 (假设图片在站点根目录下)
    if image_url and image_url.startswith('/'):
        image_url = f"{config.BASE_URL.rstrip('/')}{image_url}"
    elif not image_url:
        # 如果没有图片，可以考虑使用默认 Logo 或不设置
        image_url = None # 留空或使用默认 Logo URL
        
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post['title'],
        "description": post['summary'],
        "mainEntityOfPage": canonical_url,
        "author": {
            "@type": "Person",
            "name": config.BLOG_AUTHOR
        },
        "publisher": {
            "@type": "Organization",
            "name": config.BLOG_TITLE,
            # 可以添加 logo 信息
            # "logo": {"@type": "ImageObject", "url": "..."}
        },
        # 修复：post['date_obj'] 已经是一个 datetime 对象，可以直接使用 isoformat
        "datePublished": post['date_obj'].isoformat() if 'date_obj' in post else datetime.now(timezone.utc).isoformat(),
        "dateModified": post['date_obj'].isoformat() if 'date_obj' in post else datetime.now(timezone.utc).isoformat(),
        "url": canonical_url,
        # 估算字数
        "wordCount": len(re.sub(r'<[^>]*>', '', post['content_html']).split()), 
    }

    if image_url:
        schema['image'] = [image_url]

    return json.dumps(schema, indent=4, ensure_ascii=False)


# ------------------------------------------------------------------------
# 【核心生成函数】
# ------------------------------------------------------------------------

def is_post_hidden(post: Dict[str, Any]) -> bool:
    """检查文章是否应被隐藏。"""
    # 兼容处理，如果 post 字典不完整，则不隐藏
    return post.get('is_hidden', False)


def add_prev_next_links(posts: List[Dict[str, Any]]):
    """为排序后的文章列表添加前后文章的导航链接信息。"""
    for i, post in enumerate(posts):
        prev_post = posts[i-1] if i > 0 else None
        next_post = posts[i+1] if i < len(posts) - 1 else None

        # 转换为导航链接格式
        post['prev_post_nav'] = {
            'link': make_internal_url(prev_post['link']), 
            'title': prev_post['title']
        } if prev_post else None
        
        post['next_post_nav'] = {
            'link': make_internal_url(next_post['link']), 
            'title': next_post['title']
        } if next_post else None


def generate_post_html(post: Dict[str, Any], build_time_info: str):
    """生成单篇文章的 HTML 页面。"""
    template = env.get_template('post.html') # 假设存在 post.html 模板
    
    # post['link'] 是 posts/slug.html 格式
    canonical_path = make_internal_url(post['link']) 
    output_path_relative = canonical_path.strip('/').replace(config.SITE_ROOT.strip('/'), '', 1) 
    
    # 输出路径为 _site/posts/slug/index.html (Pretty URL 目标路径)
    output_dir = os.path.join(config.BUILD_DIR, os.path.dirname(output_path_relative))
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'index.html') 
    
    try:
        json_ld_schema = generate_post_schema(post)
    except Exception as e:
        print(f"   -> [ERROR] Failed to generate JSON-LD schema for {post['title']}: {e}")
        json_ld_schema = None
        
    context = {
        'page_id': 'post',
        'page_title': post['title'],
        'blog_title': config.BLOG_TITLE,
        'blog_description': post['summary'], # 文章页面的 description 应使用文章摘要
        'blog_author': config.BLOG_AUTHOR,
        'post': post,
        'content_html': post['content_html'], 
        'toc_html': post['toc_html'],
        'site_root': get_site_root_prefix(),
        'current_year': datetime.now().year,
        'css_filename': config.CSS_FILENAME,
        'canonical_url': f"{config.BASE_URL.rstrip('/')}{canonical_path}",
        'footer_time_info': build_time_info,
        'json_ld_schema': json_ld_schema,
        # 导航链接
        'prev_post_nav': post.get('prev_post_nav'),
        'next_post_nav': post.get('next_post_nav'),
    }

    html_content = template.render(context)
    final_html = minify_html_output(html_content)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_html)
        
    print(f"   -> Generated post: {output_path_relative}/")


def generate_index_html(posts: List[Dict[str, Any]], build_time_info: str):
    """生成主页 (Index Page)。"""
    template = env.get_template('index.html') # 假设存在 index.html 模板
    output_path = os.path.join(config.BUILD_DIR, 'index.html')

    # 仅展示最新的 MAX_POSTS_ON_INDEX 篇文章
    latest_posts = [p for p in posts if not is_post_hidden(p)][:config.MAX_POSTS_ON_INDEX]
    
    # 转换链接为 Pretty URL
    for post in latest_posts:
        post['url'] = make_internal_url(post['link'])
        
    context = {
        'page_id': 'index',
        'page_title': config.BLOG_TITLE,
        'blog_title': config.BLOG_TITLE,
        'blog_description': config.BLOG_DESCRIPTION,
        'blog_author': config.BLOG_AUTHOR,
        'posts': latest_posts,
        'site_root': get_site_root_prefix(),
        'current_year': datetime.now().year,
        'css_filename': config.CSS_FILENAME,
        'canonical_url': f"{config.BASE_URL.rstrip('/')}{make_internal_url('/')}",
        'footer_time_info': build_time_info,
        'json_ld_schema': None,
        'toc_html': '',
    }
    
    try:
        html_content = template.render(context)
        final_html = minify_html_output(html_content)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
        print(f" -> Generated: {output_path}")
    except Exception as e:
        print(f"Error generating index page: {e}")


def generate_archive_html(posts: List[Dict[str, Any]], build_time_info: str):
    """生成归档页面 (Archive Page)。"""
    template = env.get_template('archive.html') # 假设存在 archive.html 模板
    # Pretty URL 目标路径是 _site/archive/index.html
    output_dir = os.path.join(config.BUILD_DIR, 'archive')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'index.html')

    # 过滤掉隐藏文章，并转换链接为 Pretty URL
    archive_posts = []
    for post in posts:
        if not is_post_hidden(post):
            post['url'] = make_internal_url(post['link'])
            archive_posts.append(post)

    context = {
        'page_id': 'archive',
        'page_title': '归档',
        'blog_title': config.BLOG_TITLE,
        'blog_description': f"{config.BLOG_TITLE} 的文章归档。",
        'blog_author': config.BLOG_AUTHOR,
        'posts': archive_posts,
        'site_root': get_site_root_prefix(),
        'current_year': datetime.now().year,
        'css_filename': config.CSS_FILENAME,
        'canonical_url': f"{config.BASE_URL.rstrip('/')}{make_internal_url('/archive.html')}",
        'footer_time_info': build_time_info,
        'json_ld_schema': None,
        'toc_html': '',
    }
    
    try:
        html_content = template.render(context)
        final_html = minify_html_output(html_content)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
        print(f" -> Generated: {output_path}")
    except Exception as e:
        print(f"Error generating archive page: {e}")


def generate_tags_list_html(tag_map: Dict[str, List[Dict[str, Any]]], build_time_info: str):
    """生成所有标签的列表页面 (输出为 _site/tags/index.html)"""
    template = env.get_template('tags_list.html') # 假设存在 tags_list.html 模板
    
    output_dir = os.path.join(config.BUILD_DIR, config.TAGS_DIR_NAME)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'index.html')
    
    try:
        # 将 tag_map 转换为 (tag_name, post_count, tag_slug, tag_url) 列表并按文章数量降序排序
        tag_list = sorted(
            [
                (
                    name, 
                    len([p for p in posts if not is_post_hidden(p)]), # 统计可见文章数
                    tag_to_slug(name)
                ) 
                for name, posts in tag_map.items()
            ], 
            key=lambda x: x[1], 
            reverse=True
        )
        # 添加 URL
        tags_data = []
        for name, count, slug in tag_list:
            tags_data.append({
                'name': name,
                'count': count,
                # 标签页 Pretty URL 格式：/tags/slug/
                'url': make_internal_url(f'{config.TAGS_DIR_NAME}/{slug}.html')
            })

        context = {
            'page_id': 'tags-list',
            'page_title': '所有标签',
            'blog_title': config.BLOG_TITLE,
            'blog_description': f"{config.BLOG_TITLE} 的所有标签。",
            'blog_author': config.BLOG_AUTHOR,
            'tags': tags_data,
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{make_internal_url('/tags.html')}",
            'footer_time_info': build_time_info,
            'json_ld_schema': None,
            'toc_html': '',
        }
        
        html_content = template.render(context)
        final_html = minify_html_output(html_content)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
        print(f" -> Generated: {output_path}")
        
    except Exception as e:
        print(f"Error generating tags list page: {e}")


def generate_tag_page(tag: str, posts: List[Dict[str, Any]], build_time_info: str):
    """生成单个标签的文章列表页面 (输出为 _site/tags/slug/index.html)"""
    template = env.get_template('tag.html') # 假设存在 tag.html 模板
    
    tag_slug = tag_to_slug(tag)
    output_dir = os.path.join(config.BUILD_DIR, config.TAGS_DIR_NAME, tag_slug)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'index.html')
    
    # 转换文章链接为 Pretty URL
    tag_posts = []
    for post in posts:
        post['url'] = make_internal_url(post['link'])
        tag_posts.append(post)

    context = {
        'page_id': 'tag',
        'page_title': f'标签: {tag}',
        'blog_title': config.BLOG_TITLE,
        'blog_description': f"标签 '{tag}' 下的文章列表。",
        'blog_author': config.BLOG_AUTHOR,
        'tag_name': tag,
        'posts': tag_posts,
        'site_root': get_site_root_prefix(),
        'current_year': datetime.now().year,
        'css_filename': config.CSS_FILENAME,
        'canonical_url': f"{config.BASE_URL.rstrip('/')}{make_internal_url(f'{config.TAGS_DIR_NAME}/{tag_slug}.html')}",
        'footer_time_info': build_time_info,
        'json_ld_schema': None,
        'toc_html': '',
    }

    try:
        html_content = template.render(context)
        final_html = minify_html_output(html_content)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
        print(f" -> Generated tag page: {output_dir}/")
        
    except Exception as e:
        print(f"Error generating tag page for {tag}: {e}")


def generate_sitemap(posts: List[Dict[str, Any]], page_files: List[str]):
    """生成 sitemap.xml 文件。"""
    template = env.get_template('sitemap.xml') # 假设存在 sitemap.xml 模板
    output_path = os.path.join(config.BUILD_DIR, config.SITEMAP_FILE)
    
    urlset = ""
    lastmod_now = datetime.now(timezone.utc).astimezone(config.TIMEZONE_INFO).strftime('%Y-%m-%d')
    
    # 1. 添加文章链接
    for post in posts:
        if is_post_hidden(post): continue # 忽略隐藏文章
        # make_internal_url 会将 posts/slug.html 转换为 /posts/slug/
        canonical_path = make_internal_url(post['link']) 
        url = f"{config.BASE_URL.rstrip('/')}{canonical_path}"
        lastmod = post['date_obj'].strftime('%Y-%m-%d') if post.get('date_obj') else lastmod_now
        
        urlset += f""" <url>
  <loc>{url}</loc>
  <lastmod>{lastmod}</lastmod>
  <changefreq>weekly</changefreq>
  <priority>0.8</priority>
 </url>
"""

    # 2. 添加独立页面链接 (page.html -> /page.html)
    page_files_root = glob.glob(os.path.join(config.PAGES_DIR, '*.md'))
    for page_file in page_files_root:
        base_name = os.path.splitext(os.path.basename(page_file))[0]
        # 使用 /page_name.html 形式作为规范路径
        canonical_path = make_internal_url(f'/{base_name}.html') 
        url = f"{config.BASE_URL.rstrip('/')}{canonical_path}"
        
        urlset += f""" <url>
  <loc>{url}</loc>
  <lastmod>{lastmod_now}</lastmod>
  <changefreq>monthly</changefreq>
  <priority>0.5</priority>
 </url>
"""
    
    # 3. 添加主页、归档页、标签列表页
    root_links = [
        ('/', 'daily', 1.0), 
        (make_internal_url('/archive.html'), 'weekly', 0.6), 
        (make_internal_url('/tags.html'), 'weekly', 0.6)
    ]
    for path, changefreq, priority in root_links:
        url = f"{config.BASE_URL.rstrip('/')}{path}"
        urlset += f""" <url>
  <loc>{url}</loc>
  <lastmod>{lastmod_now}</lastmod>
  <changefreq>{changefreq}</changefreq>
  <priority>{priority}</priority>
 </url>
"""

    context = {
        'urlset': urlset.strip(),
    }
    
    try:
        xml_content = template.render(context)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_content.strip())
        print(f" -> Generated: {output_path}")
    except Exception as e:
        print(f"Error generating sitemap: {e}")


def generate_rss(posts: List[Dict[str, Any]], build_time: datetime):
    """生成 rss.xml 文件。"""
    template = env.get_template('rss.xml') # 假设存在 rss.xml 模板
    output_path = os.path.join(config.BUILD_DIR, config.RSS_FILE)
    
    # 仅在 RSS 中展示最新的文章
    rss_posts = [p for p in posts if not is_post_hidden(p)][:10]
    
    items = ""
    for post in rss_posts:
        # make_internal_url 会将 posts/slug.html 转换为 /posts/slug/
        canonical_path = make_internal_url(post['link'])
        post_url = f"{config.BASE_URL.rstrip('/')}{canonical_path}"
        
        # 将 date_obj 转换为 RFC 822 格式 (RSS 要求)
        pub_date = post['date_obj'].strftime('%a, %d %b %Y %H:%M:%S +0800')
        
        items += f"""  <item>
   <title>{post['title']}</title>
   <link>{post_url}</link>
   <guid isPermaLink="true">{post_url}</guid>
   <pubDate>{pub_date}</pubDate>
   <description><![CDATA[{post['content_html']}]]></description>
  </item>
"""

    context = {
        'blog_title': config.BLOG_TITLE,
        'base_url': config.BASE_URL.rstrip('/'),
        'blog_description': config.BLOG_DESCRIPTION,
        'build_time_rss': build_time.strftime('%a, %d %b %Y %H:%M:%S +0800'),
        'items': items.strip(),
    }

    try:
        xml_content = template.render(context)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_content.strip())
        print(f" -> Generated: {output_path}")
    except Exception as e:
        print(f"Error generating RSS: {e}")


# ------------------------------------------------------------------------
# 通用页面生成函数（原文件中已存在）
# ------------------------------------------------------------------------

def generate_page_html(content_html: str, page_title: str, page_id: str, canonical_path_with_html: str, build_time_info: str):
    """生成通用独立页面的 HTML。"""
    template = env.get_template('page.html') # 假设存在 page.html 模板

    # Pretty URL 目标路径，例如 /about.html -> /about/
    canonical_path = make_internal_url(canonical_path_with_html) 
    
    # 计算输出文件路径。例如 /about.html -> _site/about/index.html
    output_path_relative = canonical_path.strip('/').replace(config.SITE_ROOT.strip('/'), '', 1) 
    
    if output_path_relative.endswith('/'):
        output_dir = os.path.join(config.BUILD_DIR, output_path_relative)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'index.html')
    else:
        # 如果不是 Pretty URL，则直接输出
        output_path = os.path.join(config.BUILD_DIR, output_path_relative)


    try:
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
            'json_ld_schema': None,
            'toc_html': '', # 通用页面通常没有目录
            # 导航链接
            'prev_post_nav': None,
            'next_post_nav': None,
        }
        
        html_content = template.render(context)
        final_html = minify_html_output(html_content)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
            
        print(f"   -> Generated page: {output_path}")

    except Exception as e:
        print(f"Error generating generic page {page_id}: {e}")
