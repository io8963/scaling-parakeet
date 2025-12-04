# generator.py (完整内容，包含所有修复)

import os
import shutil 
import glob   
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Dict, Any, Tuple 
from jinja2 import Environment, FileSystemLoader
import json 
import config
from parser import tag_to_slug 

# --- Jinja2 环境配置配置 ---\
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
        """将标签名转换为 URL 友好的 slug (小写，空格变'-')。"""
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
    """
    normalized_path = path if path.startswith('/') else f'/{path}'
    site_root = get_site_root_prefix()
    
    # 组合 site_root 和 path，确保只有一个斜杠
    if site_root and normalized_path:
        return f"{site_root}{normalized_path}"
    elif site_root:
        return site_root
    else:
        return normalized_path


# --- JSON-LD 结构化数据生成 ---

def generate_webpage_json_ld(page_title: str, canonical_path: str) -> Dict[str, Any]:
    """生成基本 WebPage 的 JSON-LD 数据。"""
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "url": f"{config.BASE_URL.rstrip('/')}{make_internal_url(canonical_path)}",
        "name": f"{page_title} - {config.BLOG_TITLE}",
        "description": config.BLOG_DESCRIPTION,
        "author": {"@type": "Person", "name": config.BLOG_AUTHOR},
        "publisher": {"@type": "Person", "name": config.BLOG_AUTHOR},
    }

def generate_article_json_ld(post: Dict[str, Any]) -> Dict[str, Any]:
    """生成 Article 的 JSON-LD 数据。"""
    url = f"{config.BASE_URL.rstrip('/')}{make_internal_url(post['link'])}"
    
    # 格式化日期为 ISO 8601
    date_published_iso = post['date'].isoformat()
    date_modified_iso = post.get('last_modified', post['date']).isoformat()
    
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": url
        },
        "headline": post['title'],
        "description": post.get('excerpt', config.BLOG_DESCRIPTION),
        "image": post.get('image', f"{config.BASE_URL.rstrip('/')}/assets/default-img.jpg"), # 假设有一个默认图
        "datePublished": date_published_iso,
        "dateModified": date_modified_iso,
        "author": {"@type": "Person", "name": config.BLOG_AUTHOR},
        "publisher": {"@type": "Person", "name": config.BLOG_AUTHOR},
        "wordCount": post.get('word_count', 0),
        "articleBody": post.get('raw_content', post.get('content_markdown', ''))
    }


# --- 页面内容生成函数 ---

def generate_tags_list_html(tag_map: Dict[str, List[Dict[str, Any]]]):
    """生成所有标签的列表页面 content_html"""
    
    # NEW: 根据文章数量降序排列标签
    # tag_map.keys() 是标签名称列表
    # key=lambda t: len(tag_map[t]) 告诉 sorted() 使用文章数量作为排序标准
    sorted_tags = sorted(tag_map.keys(), key=lambda t: len(tag_map[t]), reverse=True)
    
    # 构建 HTML 内容
    # NEW: 使用 tag-list-grid 作为容器
    tags_html = "<div class=\"tag-list-grid\">"
    
    for tag in sorted_tags:
        count = len(tag_map[tag])
        slug = tag_to_slug(tag)
        # NEW: 使用 tag-card 作为每个标签的卡片
        tags_html += f"""
        <a href="{get_site_root_prefix()}/{config.TAGS_DIR_NAME}/{slug}.html" class="tag-card">
            <h3 class="tag-card-title">{tag}</h3>
            <span class="tag-card-count">共 {count} 篇文章</span>
        </a>
        """
    tags_html += "</div>"

    generate_page_html(
        content_html=tags_html,
        page_title="所有标签",
        page_id="tags",
        canonical_path="/tags.html"
    )
    print("SUCCESS: Generated tags.html.")


def generate_archive_html(all_posts: List[Dict[str, Any]]):
    """生成文章归档页面 content_html"""
    
    # 按照年份和月份对文章进行分组
    archive_map = defaultdict(lambda: defaultdict(list))
    for post in all_posts:
        year = post['date'].year
        month = post['date'].strftime('%Y-%m') # 使用 YYYY-MM 格式作为键
        archive_map[year][month].append(post)

    # 按年份降序排序
    sorted_years = sorted(archive_map.keys(), reverse=True)
    
    archive_html = "<div class=\"archive-list\">"
    
    for year in sorted_years:
        archive_html += f"<h2>{year} 年</h2>"
        # 按月份降序排序
        sorted_months = sorted(archive_map[year].keys(), reverse=True)
        
        for month_key in sorted_months:
            # 排序文章（最新在前）
            posts_in_month = sorted(
                archive_map[year][month_key], 
                key=lambda p: p['date'], 
                reverse=True
            )
            
            # 使用月份的中文表示，例如 "2024年03月"
            month_display = datetime.strptime(month_key, '%Y-%m').strftime('%Y年%m月')
            
            archive_html += f"<h3>{month_display} ({len(posts_in_month)} 篇)</h3>"
            
            # 使用与首页列表相同的 post-list 结构
            archive_html += "<ul class=\"post-list\">"
            for post in posts_in_month:
                archive_html += f"""
                    <a href="{get_site_root_prefix()}/{post['link']}" class="post-list-item">
                        <div class="post-content-wrapper">
                            <h2 class="post-title">{post['title']}</h2>
                            
                            {f'<p class="post-excerpt">{post["excerpt"]}</p>' if post.get('excerpt') else ''}
                        </div>

                        <div class="post-meta-list">
                            <span class="meta-date">🗓 {post['date_formatted']}</span>
                            
                            {'<div class="meta-tags list-tags"><ul class="tags-list">' if post.get('tags') else ''}
                            {
                                "".join(f'<li><span class="tag-badge">{tag["name"]}</span></li>' 
                                        for tag in post.get('tags', []))
                            }
                            {'</ul></div>' if post.get('tags') else ''}
                        </div>
                    </a>
                """
            archive_html += "</ul>"
            
    archive_html += "</div>"

    generate_page_html(
        content_html=archive_html,
        page_title="文章归档",
        page_id="archive",
        canonical_path="/archive.html"
    )
    print("SUCCESS: Generated archive.html.")


def generate_tag_page(tag_name: str, posts: List[Dict[str, Any]]):
    """生成单个标签的文章列表页面"""
    slug = tag_to_slug(tag_name)
    output_path = os.path.join(config.BUILD_DIR, config.TAGS_DIR_NAME, f'{slug}.html')
    
    template = env.get_template('base.html')
    
    # JSON-LD for Tag Page (WebPage type)
    canonical_path = f"{config.TAGS_DIR_NAME}/{slug}.html"
    json_ld_schema = json.dumps(generate_webpage_json_ld(f"标签: {tag_name}", canonical_path), ensure_ascii=False, indent=2)

    context = {
        'page_id': 'tag',
        'page_title': f"标签: {tag_name}",
        'tag': tag_name, # 用于在 base.html 中显示标签名
        'posts': posts,
        'blog_title': config.BLOG_TITLE,
        'blog_description': config.BLOG_DESCRIPTION,
        'blog_author': config.BLOG_AUTHOR,
        'site_root': get_site_root_prefix(),
        'current_year': datetime.now().year,
        'css_filename': config.CSS_FILENAME,
        'canonical_url': f"{config.BASE_URL.rstrip('/')}{make_internal_url(canonical_path)}",
        'footer_time_info': f"Build time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        'json_ld_schema': json_ld_schema
    }
    
    html_content = template.render(context)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)


def generate_post_page(post: Dict[str, Any]):
    """生成单篇文章页面"""
    output_path = os.path.join(config.BUILD_DIR, post['link'])
    
    # 确保 posts 目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    template = env.get_template('base.html')
    
    # 提取文章的元数据
    post_date_formatted = post['date'].strftime('%Y 年 %m 月 %d 日')
    
    # JSON-LD for Article Page
    json_ld_schema = json.dumps(generate_article_json_ld(post), ensure_ascii=False, indent=2)

    context = {
        'page_id': 'post',
        'page_title': post['title'],
        'post': post,
        'content_html': post['content_html'],
        'toc_html': post.get('toc_html', ''),
        'post_date': post_date_formatted,
        'post_tags': post.get('tags', []),
        'blog_title': config.BLOG_TITLE,
        'blog_description': config.BLOG_DESCRIPTION,
        'blog_author': config.BLOG_AUTHOR,
        'site_root': get_site_root_prefix(),
        'current_year': datetime.now().year,
        'css_filename': config.CSS_FILENAME,
        'canonical_url': f"{config.BASE_URL.rstrip('/')}{make_internal_url(post['link'])}",
        'footer_time_info': f"Build time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        'json_ld_schema': json_ld_schema,
    }
    
    html_content = template.render(context)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)


def generate_index_page(posts: List[Dict[str, Any]]):
    """生成首页 (index.html)"""
    
    template = env.get_template('base.html')
    
    # JSON-LD for Index Page
    json_ld_schema = json.dumps(generate_webpage_json_ld("首页", "/index.html"), ensure_ascii=False, indent=2)

    context = {
        'page_id': 'index',
        'page_title': "首页",
        'posts': posts,
        'max_posts_on_index': config.MAX_POSTS_ON_INDEX, # 用于判断是否显示 '查看全部归档' 按钮
        'blog_title': config.BLOG_TITLE,
        'blog_description': config.BLOG_DESCRIPTION,
        'blog_author': config.BLOG_AUTHOR,
        'site_root': get_site_root_prefix(),
        'current_year': datetime.now().year,
        'css_filename': config.CSS_FILENAME,
        'canonical_url': f"{config.BASE_URL.rstrip('/')}{make_internal_url('/index.html')}",
        'footer_time_info': f"Build time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        'json_ld_schema': json_ld_schema,
    }
    
    html_content = template.render(context)
    
    output_path = os.path.join(config.BUILD_DIR, 'index.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print("SUCCESS: Generated index.html.")


def generate_page_html(content_html: str, page_title: str, page_id: str, canonical_path: str):
    """生成通用页面 (如 about.html)"""
    try:
        output_path = os.path.join(config.BUILD_DIR, f'{page_id}.html')
        
        template = env.get_template('base.html')
        
        # JSON-LD for Generic Page
        json_ld_schema = json.dumps(generate_webpage_json_ld(page_title, canonical_path), ensure_ascii=False, indent=2)
        
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
            'json_ld_schema': json_ld_schema
        }
        
        html_content = template.render(context)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"SUCCESS: Generated {page_id}.html.")

    except Exception as e:
        print(f"Error generating {page_id}.html: {type(e).__name__}: {e}")


# --- 特殊文件生成 ---

def generate_robots_txt():
    """生成 robots.txt"""
    content = f"""
User-agent: *
Allow: /

Sitemap: {config.BASE_URL.rstrip('/')}{make_internal_url(config.SITEMAP_FILE)}
"""
    output_path = os.path.join(config.BUILD_DIR, 'robots.txt')
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content.strip())
        print("SUCCESS: Generated robots.txt.")
    except Exception as e:
        print(f"Error generating robots.txt: {e}")


def generate_sitemap(all_posts: List[Dict[str, Any]]) -> str:
    """生成 sitemap.xml"""
    base_url_normalized = config.BASE_URL.rstrip('/')
    sitemap_file_url = make_internal_url(config.SITEMAP_FILE)

    urls = []
    # 1. 首页
    urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url('/index.html')}</loc>
        <lastmod>{datetime.now(timezone.utc).date().isoformat()}</lastmod>
        <changefreq>daily</changefreq>
        <priority>1.0</priority>
    </url>
    """)
    # 2. 归档和标签列表页
    for page in ['archive.html', 'tags.html', 'about.html']:
        urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url(f'/{page}')}</loc>
        <lastmod>{datetime.now(timezone.utc).date().isoformat()}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>
    </url>
    """)
    
    # 3. 所有文章页
    for post in all_posts:
        last_mod = post.get('last_modified', post['date']).date().isoformat()
        urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url(post['link'])}</loc>
        <lastmod>{last_mod}</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.6</priority>
    </url>
    """)

    # 4. 所有标签的文章列表页 (需要从所有文章中提取标签并去重)
    all_tags = set()
    for post in all_posts:
        for tag in post.get('tags', []):
            all_tags.add(tag['name'])
            
    for tag_name in all_tags:
        slug = tag_to_slug(tag_name)
        urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url(f'/{config.TAGS_DIR_NAME}/{slug}.html')}</loc>
        <lastmod>{datetime.now(timezone.utc).date().isoformat()}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>0.5</priority>
    </url>
    """)

    sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    {"".join(urls).strip()}
</urlset>"""
    return sitemap_content


def generate_rss(all_posts: List[Dict[str, Any]]):
    """生成 rss.xml"""
    base_url_normalized = config.BASE_URL.rstrip('/')
    rss_file_url = make_internal_url(config.RSS_FILE)

    items = []
    # 只取最新的 N 篇文章
    for post in all_posts[:config.RSS_FEED_MAX_ITEMS]:
        pub_date = post['date'].strftime('%a, %d %b %Y %H:%M:%S +0000')
        item_url = f"{base_url_normalized}{make_internal_url(post['link'])}"
        
        # 完整的文章内容 (HTML)
        # 确保内容在 XML 中是 CDATA 包裹，防止解析错误
        content = post['content_html']
        
        item = f"""
<item>
    <title>{post['title']}</title>
    <link>{item_url}</link>
    <guid isPermaLink="true">{item_url}</guid>
    <pubDate>{pub_date}</pubDate>
    <description><![CDATA[{post.get('excerpt', post['title'])}]]></description>
    <content:encoded><![CDATA[{content}]]></content:encoded>
    <author>{config.BLOG_AUTHOR}</author>
</item>"""
        items.append(item)

    rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
    <title>{config.BLOG_TITLE}</title>
    <link>{base_url_normalized}{get_site_root_prefix()}</link>
    <description>{config.BLOG_DESCRIPTION}</description>
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
        
        # JSON-LD for Generic Page
        json_ld_schema = json.dumps(generate_webpage_json_ld(page_title, canonical_path), ensure_ascii=False, indent=2)

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
            'json_ld_schema': json_ld_schema
        }
        
        html_content = template.render(context)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"SUCCESS: Generated {page_id}.html.")

    except Exception as e:
        print(f"Error generating {page_id}.html: {type(e).__name__}: {e}")
