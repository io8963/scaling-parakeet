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

# --- Jinja2 环境配置配置 ---
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=True,
    trim_blocks=True, 
    lstrip_blocks=True
)

# --- 辅助函数：路径和 URL ---

def tag_to_slug(tag_name: str) -> str:
    """将标签名转换为 URL 友好的 slug (小写，空格变'-')。"""
    return tag_name.lower().replace(' ', '-')

def get_site_root_prefix() -> str:
    """
    获取网站在部署环境中的相对子目录路径前缀。
    用于在模板中拼接内部链接。
    如果 REPO_SUBPATH 为空，则返回空字符串 ''。
    如果 REPO_SUBPATH 为 'blog'，则返回 '/blog'。
    """
    root = config.REPO_SUBPATH.strip()
    if not root or root == '/':
        return ''
    # 确保它不以 '/' 结尾，但以 '/' 开头
    root = root.rstrip('/')
    return root if root.startswith('/') else f'/{root}'

def make_internal_url(path: str) -> str:
    """
    生成一个以相对 SITE_ROOT 为基础的规范化内部 URL。
    结果格式为 /subpath/path 或 /path。
    """
    site_root_prefix = get_site_root_prefix()
    path_without_leading_slash = path.lstrip('/')
    
    if not path_without_leading_slash:
        # 如果路径是空的 ('')，则返回根路径 (例如 '/' 或 '/blog')
        return site_root_prefix if site_root_prefix else '/'

    # 结果格式为 /subpath/path 或 /path
    return f"{site_root_prefix}/{path_without_leading_slash}"

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
        # 此处我们只复制，实际的 CSS 复制和哈希已在 autobuild.py 中处理
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

# generate_about_page (应用 site_root 修正)
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
            # 修正：使用正确的相对路径前缀
            site_root=get_site_root_prefix(), 
            canonical_url=config.BASE_URL.rstrip('/') + make_internal_url(link), 
            css_filename=config.CSS_FILENAME,
            # ... (通用变量保持不变) ...
            
            content_html=content_with_title,
            # ...
        )

        output_path = os.path.join(config.BUILD_DIR, config.ABOUT_OUTPUT_FILE)
        # ... (文件写入逻辑保持不变) ...
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"SUCCESS: Generated special page {config.ABOUT_OUTPUT_FILE}.")
    
    except Exception as e:
        print(f"Error generating about page: {type(e).__name__}: {e}")

# generate_post_html (应用 site_root 修正)
def generate_post_html(post: Dict[str, Any]):
    """为单篇文章生成 HTML 页面"""
    try:
        template = env.get_template('base.html')
        
        # ... (JSON-LD Schema 保持不变) ...
        
        post_tags_data = post.get('tags', []) 
        
        html_content = template.render(
            page_id='post',
            page_title=post['title'],
            # 修正：使用正确的相对路径前缀
            site_root=get_site_root_prefix(),
            canonical_url=config.BASE_URL.rstrip('/') + make_internal_url(post['link']),
            css_filename=config.CSS_FILENAME,
            # ... (通用变量保持不变) ...
            
            content_html=post['content_html'],
            # ...
        )

        output_path = os.path.join(config.BUILD_DIR, post['link'].lstrip('/'))
        # ... (文件写入逻辑保持不变) ...
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated post: {post['link']}")

    except Exception as e:
        print(f"Error generating post '{post.get('title', 'Unknown')}' HTML: {type(e).__name__}: {e}")


# generate_index_html (应用 site_root 修正)
def generate_index_html(all_posts: List[Dict[str, Any]]):
    """生成首页 index.html"""
    try:
        visible_posts = [p for p in all_posts if not is_post_hidden(p)] 
        posts_for_index = visible_posts[:config.MAX_POSTS_ON_INDEX] 
        template = env.get_template('base.html')
        
        html_content = template.render(
            page_id='index',
            page_title=config.BLOG_TITLE,
            # 修正：使用正确的相对路径前缀
            site_root=get_site_root_prefix(),
            canonical_url=config.BASE_URL.rstrip('/') + make_internal_url('/'),
            css_filename=config.CSS_FILENAME,
            # ... (通用变量保持不变) ...
            
            posts=posts_for_index,
            # ...
        )

        output_path = os.path.join(config.BUILD_DIR, config.INDEX_FILE)
        # ... (文件写入逻辑保持不变) ...
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated {config.INDEX_FILE}.")
    
    except Exception as e:
        print(f"Error generating index.html: {type(e).__name__}: {e}")


# generate_archive_html (应用 site_root 修正)
def generate_archive_html(all_posts: List[Dict[str, Any]]):
    """生成归档页 archive.html (显示所有可见文章)"""
    try:
        visible_posts = [p for p in all_posts if not is_post_hidden(p)]
        template = env.get_template('base.html')
        
        # ... (archive_map 构建保持不变) ...
        archive_map = defaultdict(list)
        for post in visible_posts:
            year = post['date'].year
            archive_map[year].append(post)
            
        sorted_archive = sorted(archive_map.items(), key=lambda x: x[0], reverse=True)
            
        # 渲染归档页内容 (手动构建 content_html)
        content_html = "<h1>文章归档</h1>\n"
        for year, posts in sorted_archive:
            content_html += f"<h2>{year} ({len(posts)} 篇)</h2>\n<ul class=\"archive-list\">\n"
            sorted_posts = sorted(posts, key=lambda p: p['date'], reverse=True)
            for post in sorted_posts:
                # 修正：使用 make_internal_url 确保链接正确
                link = make_internal_url(post['link']) 
                date_str = post['date'].strftime('%Y-%m-%d')
                content_html += f"  <li><span class=\"archive-date\">{date_str}</span> - <a href=\"{link}\">{post['title']}</a></li>\n"
            content_html += "</ul>\n"
            
        html_content = template.render(
            page_id='archive',
            page_title='文章归档',
            # 修正：使用正确的相对路径前缀
            site_root=get_site_root_prefix(),
            canonical_url=config.BASE_URL.rstrip('/') + make_internal_url(config.ARCHIVE_FILE),
            css_filename=config.CSS_FILENAME,
            # ... (通用变量保持不变) ...
            
            content_html=content_html,
            # ...
        )

        output_path = os.path.join(config.BUILD_DIR, config.ARCHIVE_FILE)
        # ... (文件写入逻辑保持不变) ...
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated {config.ARCHIVE_FILE}.")

    except Exception as e:
        print(f"Error generating archive.html: {type(e).__name__}: {e}")


# generate_tags_list_html (应用 site_root 修正)
def generate_tags_list_html(tag_map: Dict[str, List[Dict[str, Any]]]):
    """生成所有标签的列表页 tags.html"""
    try:
        filtered_tag_map = defaultdict(list)
        for tag, posts in tag_map.items():
            visible_posts = [p for p in posts if not is_post_hidden(p)]
            if visible_posts:
                filtered_tag_map[tag].extend(visible_posts)

        template = env.get_template('base.html')
        
        # ... (content_html 构建保持不变) ...
        content_html = "<h1>所有标签</h1>\n"
        content_html += "<ul class=\"tags-cloud-list\">\n"
        sorted_tags = sorted(filtered_tag_map.items(), key=lambda item: len(item[1]), reverse=True)
        
        for tag, posts in sorted_tags:
            tag_slug = tag_to_slug(tag)
            # 修正：使用 make_internal_url 确保链接正确
            tag_link = make_internal_url(os.path.join(config.TAGS_DIR, f'{tag_slug}.html')) 
            content_html += f"  <li><a href=\"{tag_link}\" class=\"tag-cloud-item\">{tag}</a> ({len(posts)} 篇)</li>\n"
        content_html += "</ul>\n"
        
        html_content = template.render(
            page_id='tags',
            page_title='所有标签',
            # 修正：使用正确的相对路径前缀
            site_root=get_site_root_prefix(),
            canonical_url=config.BASE_URL.rstrip('/') + make_internal_url(config.TAGS_LIST_FILE),
            css_filename=config.CSS_FILENAME,
            # ... (通用变量保持不变) ...
            
            content_html=content_html,
            # ...
        )

        output_path = os.path.join(config.BUILD_DIR, config.TAGS_LIST_FILE)
        # ... (文件写入逻辑保持不变) ...
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"SUCCESS: Generated {config.TAGS_LIST_FILE}.")

    except Exception as e:
        print(f"Error generating tags.html: {type(e).__name__}: {e}")


# generate_tag_page (应用 site_root 修正)
def generate_tag_page(tag: str, all_tag_posts: List[Dict[str, Any]]):
    """为单个标签生成页面"""
    try:
        visible_tag_posts = [p for p in all_tag_posts if not is_post_hidden(p)]
        
        # ... (调试输出和跳过逻辑保持不变) ...
        
        if not visible_tag_posts:
            print(f"INFO: Skipping tag '{tag}' page generation as all posts are hidden/empty.")
            return 
            
        template = env.get_template('base.html')
        tag_slug = tag_to_slug(tag)
        output_filename = f'{tag_slug}.html'
        
        # 2. 渲染模板
        html_content = template.render(
            page_id='tag', 
            page_title=f"标签: {tag}",
            # 修正：使用正确的相对路径前缀
            site_root=get_site_root_prefix(),
            canonical_url=config.BASE_URL.rstrip('/') + make_internal_url(os.path.join(config.TAGS_DIR, output_filename)),
            css_filename=config.CSS_FILENAME,
            # ... (通用变量保持不变) ...
            
            tag=tag,
            posts=visible_tag_posts, 
            # ...
        )

        output_path = os.path.join(config.TAGS_OUTPUT_DIR, output_filename)
        
        # ... (文件写入逻辑保持不变) ...
        output_dir = os.path.dirname(output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"SUCCESS: Generated tag page: {output_path} (URL: tags/{output_filename}).")

    except Exception as e:
        print(f"Error generating tag page for '{tag}': {type(e).__name__}: {e}")

# ... (XML/RSS 生成函数和文件复制函数保持不变) ...


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
