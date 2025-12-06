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
    if path.startswith('/'):
        # 对于根路径链接 (如 /archive/)
        return f"{config.SITE_ROOT}{path}"
    
    # 转换为 Pretty URL 结构 (posts/slug.html -> posts/slug/)
    if path.endswith('.html'):
        path = path[:-5] # 移除 .html
        path = path.replace(f"{config.POSTS_DIR_NAME}/", f"{config.POSTS_DIR_NAME}/") # 保持 posts/ 前缀
        path += '/' # 加上尾部斜杠

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
        "@context": "[https://schema.org](https://schema.org)",
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
        "datePublished": post['date_obj'].isoformat() if 'date_obj' in post else datetime.now(timezone.utc).isoformat(),
        "dateModified": post['date_obj'].isoformat() if 'date_obj' in post else datetime.now(timezone.utc).isoformat(),
        "url": canonical_url,
        "wordCount": len(re.sub(r'<[^>]*>', '', post['content_html']).split()), # 估算字数
    }
    
    if image_url:
        schema['image'] = [image_url]

    return json.dumps(schema, indent=4, ensure_ascii=False)


# --- 核心生成函数 ---

def generate_post_page(post: Dict[str, Any]):
    """生成单篇文章页面 (输出为 posts/slug/index.html)"""
    try:
        # 强制转换为 directory/index.html 结构
        output_dir = os.path.join(config.BUILD_DIR, config.POSTS_DIR_NAME, post['slug'])
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'index.html')
        
        template = env.get_template('post.html')
        
        # 文章链接转换为 Pretty URL，用于 canonical
        canonical_path_with_html = post['link'] 
        canonical_path = make_internal_url(canonical_path_with_html) 
        
        context = {
            'page_id': 'post',
            'page_title': post['title'],
            'blog_title': config.BLOG_TITLE,
            'blog_description': post['summary'], # 文章描述使用文章摘要
            'blog_author': config.BLOG_AUTHOR,
            'post': post,
            'content_html': post['content_html'],
            'toc_html': post.get('toc_html', ''),
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{canonical_path}",
            'footer_time_info': post['footer_time_info'], # 使用 Git/构建时间
            'json_ld_schema': generate_post_schema(post),
            # 导航链接已在 autobuild.py 中处理并存入 post 字典
            'prev_post_nav': post.get('prev_post_nav'),
            'next_post_nav': post.get('next_post_nav'),
        }
        
        html_content = template.render(context)
        final_html = minify_html_output(html_content)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
            
        print(f"   -> Generated post: {output_path}")

    except Exception as e:
        print(f"Error generating post page {post.get('slug', 'unknown')}: {e}")


def generate_index_html(all_posts: List[Dict[str, Any]], build_time_info: str):
    """生成首页 (输出为 _site/index.html)"""
    try:
        # 筛选出要显示在首页的文章 (非草稿，最多 MAX_POSTS_ON_INDEX 篇)
        # 确保只包含 status='published' 或没有 status 字段的文章
        published_posts = [p for p in all_posts if not is_post_hidden(p)]
        
        # ⭐ 修复：使用 config.MAX_POSTS_ON_INDEX
        posts_on_index = published_posts[:config.MAX_POSTS_ON_INDEX]
        
        template = env.get_template('index.html')
        output_path = os.path.join(config.BUILD_DIR, 'index.html')
        
        canonical_path = make_internal_url('index.html') 
        
        context = {
            'page_id': 'index',
            'page_title': config.BLOG_TITLE,
            'blog_title': config.BLOG_TITLE,
            'blog_description': config.BLOG_DESCRIPTION,
            'blog_author': config.BLOG_AUTHOR,
            'posts': posts_on_index,
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{canonical_path}",
            'footer_time_info': build_time_info,
            'show_more_link': len(published_posts) > config.MAX_POSTS_ON_INDEX, # 检查是否需要显示 '更多文章' 链接
            'json_ld_schema': None # 首页通常不需要 Article Schema
        }
        
        html_content = template.render(context)
        final_html = minify_html_output(html_content)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
            
        print(f"   -> Generated: {output_path}")

    except Exception as e:
        print(f"Error index.html: {e}")


def generate_archive_html(all_posts: List[Dict[str, Any]], build_time_info: str):
    """生成归档页面 (输出为 _site/archive/index.html)"""
    try:
        # 仅归档已发布的文章
        published_posts = [p for p in all_posts if not is_post_hidden(p)]
        
        # 按年份分组
        archive_map = defaultdict(list)
        for post in published_posts:
            year = post['date'].year # post['date'] 是 datetime.date 对象
            archive_map[year].append(post)
            
        # 按年份降序排序
        sorted_archive = sorted(archive_map.items(), key=lambda x: x[0], reverse=True)
            
        template = env.get_template('archive.html')
        output_dir = os.path.join(config.BUILD_DIR, 'archive')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'index.html')
        
        canonical_path = make_internal_url('archive.html') 
        
        context = {
            'page_id': 'archive',
            'page_title': '文章归档',
            'blog_title': config.BLOG_TITLE,
            'blog_description': '所有文章的归档列表',
            'blog_author': config.BLOG_AUTHOR,
            'archive_list': sorted_archive,
            'total_posts': len(published_posts),
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{canonical_path}",
            'footer_time_info': build_time_info,
            'json_ld_schema': None
        }
        
        html_content = template.render(context)
        final_html = minify_html_output(html_content)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
            
        print(f"   -> Generated: {output_path}")

    except Exception as e:
        print(f"Error generating archive page: {e}")
        
        
def generate_tags_list_html(tag_map: Dict[str, List[Dict[str, Any]]], build_time_info: str):
    """生成所有标签的列表页面 (输出为 _site/tags/index.html)"""
    try:
        # 将 tag_map 转换为 (tag_name, post_count) 列表并按文章数量降序排序
        tag_list = sorted(
            [(name, len(posts)) for name, posts in tag_map.items()], 
            key=lambda x: x[1], 
            reverse=True
        )
        
        template = env.get_template('tags_list.html')
        output_dir = os.path.join(config.BUILD_DIR, config.TAGS_DIR_NAME)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'index.html')
        
        canonical_path = make_internal_url(f'{config.TAGS_DIR_NAME}.html') 

        context = {
            'page_id': 'tags-list',
            'page_title': '标签列表',
            'blog_title': config.BLOG_TITLE,
            'blog_description': '所有文章标签的列表',
            'blog_author': config.BLOG_AUTHOR,
            'tag_list': tag_list,
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{canonical_path}",
            'footer_time_info': build_time_info,
            'json_ld_schema': None
        }
        
        html_content = template.render(context)
        final_html = minify_html_output(html_content)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
            
        print(f"   -> Generated: {output_path}")

    except Exception as e:
        print(f"Error generating tags list page: {e}")


def generate_tag_page(tag_name: str, posts: List[Dict[str, Any]], build_time_info: str):
    """生成单个标签页面 (输出为 _site/tags/tag-slug/index.html)"""
    try:
        tag_slug = tag_to_slug(tag_name)
        
        template = env.get_template('tag.html')
        # [文件输出路径]
        output_dir = os.path.join(config.BUILD_DIR, config.TAGS_DIR_NAME, tag_slug)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'index.html')
        
        # [URL] 标签链接转换为 Pretty URL
        canonical_path_with_html = f'{config.TAGS_DIR_NAME}/{tag_slug}.html'
        canonical_path = make_internal_url(canonical_path_with_html) 
        
        context = {
            'page_id': 'tag',
            'page_title': f'标签：{tag_name}',
            'blog_title': config.BLOG_TITLE,
            'blog_description': f'标签 "{tag_name}" 下的所有文章',
            'blog_author': config.BLOG_AUTHOR,
            'tag_name': tag_name,
            'posts': posts,
            'site_root': get_site_root_prefix(),
            'current_year': datetime.now().year,
            'css_filename': config.CSS_FILENAME,
            'canonical_url': f"{config.BASE_URL.rstrip('/')}{canonical_path}",
            'footer_time_info': build_time_info,
            'json_ld_schema': None
        }
        
        html_content = template.render(context)
        final_html = minify_html_output(html_content)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
            
        print(f"   -> Generated tag page: {output_path}")

    except Exception as e:
        print(f"Error generating tag page for {tag_name}: {e}")


def generate_robots_txt():
    """生成 robots.txt"""
    try:
        output_path = os.path.join(config.BUILD_DIR, 'robots.txt')
        content = (
            f"User-agent: *\n"
            f"Allow: /\n"
            f"Sitemap: {config.BASE_URL.rstrip('/')}{config.SITE_ROOT}/{config.SITEMAP_FILE}\n"
        )
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"   -> Generated: {output_path}")
    except Exception as e:
        print(f"Error generating robots.txt: {e}")


def generate_sitemap(all_posts: List[Dict[str, Any]]) -> str:
    """生成 Sitemap XML (不进行 HTML Minify)"""
    # 仅包含已发布的文章
    published_posts = [p for p in all_posts if not is_post_hidden(p)]

    urlset = f'<urlset xmlns="[http://www.sitemaps.org/schemas/sitemap/0.9](http://www.sitemaps.org/schemas/sitemap/0.9)">'
    
    # 1. 首页 URL
    urlset += f"""
<url>
    <loc>{config.BASE_URL.rstrip('/')}{config.SITE_ROOT}/</loc>
    <lastmod>{datetime.now(timezone.utc).date().isoformat()}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
</url>
"""

    # 2. 归档页和标签列表页
    for path in ['archive', 'tags']:
        urlset += f"""
<url>
    <loc>{config.BASE_URL.rstrip('/')}{make_internal_url(f'{path}.html')}</loc>
    <lastmod>{datetime.now(timezone.utc).date().isoformat()}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
</url>
"""
        
    # 3. 文章 URL
    for post in published_posts:
        lastmod = post.get('date_obj', datetime.now(timezone.utc).date()).isoformat()
        urlset += f"""
<url>
    <loc>{config.BASE_URL.rstrip('/')}{make_internal_url(post['link'])}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
</url>
"""

    # 4. 通用页面 (需要 config.PAGES_DIR 存在)
    if os.path.exists(config.PAGES_DIR):
        page_files = glob.glob(os.path.join(config.PAGES_DIR, '*.md'))
        for page_file in page_files:
            base_name = os.path.splitext(os.path.basename(page_file))[0]
            canonical_path = make_internal_url(f'{base_name}.html')
            urlset += f"""
<url>
    <loc>{config.BASE_URL.rstrip('/')}{canonical_path}</loc>
    <lastmod>{datetime.now(timezone.utc).date().isoformat()}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
</url>
"""

    urlset += "</urlset>"
    return urlset

def generate_rss(all_posts: List[Dict[str, Any]]) -> str:
    """生成 RSS 订阅 XML (不进行 HTML Minify)"""
    # 仅包含最新的 10 篇已发布的文章
    published_posts = [p for p in all_posts if not is_post_hidden(p)][:10]
    
    items = []
    for post in published_posts:
        link = f"{config.BASE_URL.rstrip('/')}{make_internal_url(post['link'])}"
        pub_date = post.get('date_obj', datetime.now(timezone.utc)).astimezone(timezone.utc)
        
        items.append(f"""
    <item>
        <title>{post['title']}</title>
        <link>{link}</link>
        <guid isPermaLink="true">{link}</guid>
        <pubDate>{pub_date.strftime("%a, %d %b %Y %H:%M:%S +0000")}</pubDate>
        <description><![CDATA[{post['content_html']}]]></description>
    </item>
""")

    # 获取最新一篇文章的发布时间作为 lastBuildDate
    last_build_date = published_posts[0].get('date_obj', datetime.now(timezone.utc)).astimezone(timezone.utc) if published_posts else datetime.now(timezone.utc)
    
    return f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0" xmlns:atom="[http://www.w3.org/2005/Atom](http://www.w3.org/2005/Atom)"><channel><title>{config.BLOG_TITLE}</title><link>{config.BASE_URL.rstrip("/")}{config.SITE_ROOT}/</link><atom:link href="{config.BASE_URL.rstrip("/")}{config.SITE_ROOT}/{config.RSS_FILE}" rel="self" type="application/rss+xml" /><description>{config.BLOG_DESCRIPTION}</description><language>zh-cn</language><lastBuildDate>{last_build_date.strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>{"".join(items)}</channel></rss>'


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

# 【重要：由于 generate_index_html 中使用了 is_post_hidden，它必须在 generator.py 中定义或导入】
# 因为 is_post_hidden 逻辑在 autobuild.py 和 generator.py 中都被需要，
# 我们暂时将它保留在 generator.py 中，以防万一。
def is_post_hidden(post: Dict[str, Any]) -> bool:
    """检查文章是否应被隐藏。"""
    # 假设 post 是一个 Dict[str, Any]
    return post.get('status', 'published').lower() == 'draft' or post.get('hidden') is True
