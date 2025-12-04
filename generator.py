# generator.py

import os
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Dict, Any
from jinja2 import Environment, FileSystemLoader

# 导入配置
import config

# --- Jinja2 环境配置 ---
# 设置模板目录
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=True, # 开启自动转义，防止 XSS
    trim_blocks=True, # 自动去除块标签后的换行符
    lstrip_blocks=True # 自动去除块标签前的空白
)

# --- 辅助函数 ---

def get_site_root():
    """返回规范化的 SITE_ROOT，用于路径拼接，确保不以斜杠结尾（除非是空字符串）。"""
    root = config.BASE_URL
    if not root or root == '/':
        return ''
    return root.rstrip('/') # 移除尾部斜杠

def make_internal_url(path: str) -> str:
    """生成一个以 SITE_ROOT 为基础的规范化内部 URL，以 / 开头。"""
    site_root = get_site_root()
    
    # 移除输入 path 的头部斜杠
    path_without_leading_slash = path.lstrip('/')
    
    # 如果 site_root 为空，直接返回以 / 开头的路径
    if not site_root:
        if not path_without_leading_slash:
            return '/'
        return '/' + path_without_leading_slash
    
    # 如果 site_root 不为空，则返回 site_root + / + path_without_leading_slash
    if not path_without_leading_slash:
        return site_root + '/'
    
    return site_root + '/' + path_without_leading_slash

def generate_page_title(page_id: str, post_data: Dict[str, Any] = None) -> str:
    """根据页面类型生成浏览器 <title> 标签内容"""
    if page_id == 'index':
        return '首页'
    elif page_id == 'archive':
        return '文章归档'
    elif page_id == 'tags':
        return '所有标签'
    elif page_id == 'tag-page' and post_data:
        return f"标签: {post_data}"
    elif page_id == 'about':
        return '关于我'
    elif page_id == 'post' and post_data and post_data.get('title'):
        return post_data['title']
    return '页面'


def regenerate_html_file(
    output_path: str,
    # 通用变量
    page_id: str,
    page_title: str,
    canonical_url: str,
    current_year: int,
    site_root: str,
    # 博客信息
    blog_title: str,
    blog_description: str,
    blog_author: str,
    lang: str = 'zh-Hans',
    # 文章/列表页特定变量
    main_title_html: str = '',
    content_html: str = '',
    # 文章详情页特定变量
    post_date: str = '',
    post_tags: List[Dict[str, str]] = None,
    # 页脚时间信息
    footer_time_info: str = '',
    # 目录变量
    toc_html: str = ''
):
    """使用 Jinja2 渲染并写入 HTML 文件"""
    
    try:
        # 获取模板
        template = env.get_template('base.html')
        
        # 渲染模板
        rendered_html = template.render(
            page_id=page_id,
            page_title=page_title,
            canonical_url=canonical_url,
            current_year=current_year,
            site_root=site_root,
            blog_title=blog_title,
            blog_description=blog_description,
            blog_author=blog_author,
            lang=lang,
            main_title_html=main_title_html,
            content_html=content_html,
            post_date=post_date,
            post_tags=post_tags, # 直接传递列表，Jinja2 在模板中循环处理
            footer_time_info=footer_time_info,
            toc_html=toc_html
        )

        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(rendered_html)
            
    except Exception as e:
        print(f"ERROR: Could not render/write HTML file {output_path}: {e}")


# --- 核心生成函数 ---

def generate_post_html(post_data: Dict[str, Any]):
    """生成单篇文章的 HTML 详情页"""
    
    post_slug = post_data['slug']
    post_title = post_data['title']
    
    internal_path = os.path.join(config.POSTS_DIR, f'{post_slug}.html')
    output_path = os.path.join(config.BUILD_DIR, internal_path)
    canonical_url = make_internal_url(internal_path)
    
    main_title_html = f"<h1>{post_title}</h1>"
    post_date_str = post_data['date'].astimezone(timezone.utc).strftime('%Y-%m-%d')
    
    now_utc = datetime.now(timezone.utc)
    time_label = "生成于" if post_data['date'] != now_utc else "发布于" 
    post_time_utc_str = now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')
    footer_time_info_str = f"{time_label}: {post_time_utc_str}" 
    
    regenerate_html_file(
        output_path=output_path,
        page_id='post',
        page_title=generate_page_title('post', post_data),
        canonical_url=canonical_url,
        current_year=datetime.now().year,
        site_root=config.SITE_ROOT,
        blog_title=config.BLOG_TITLE,
        blog_description=config.BLOG_DESCRIPTION,
        blog_author=config.BLOG_AUTHOR,
        main_title_html=main_title_html,
        content_html=post_data['content_html'],
        post_date=post_date_str,
        post_tags=post_data.get('tags'),
        footer_time_info=footer_time_info_str,
        toc_html=post_data.get('toc_html', '') 
    )


def generate_index_html(parsed_posts: List[Dict[str, Any]]):
    """生成首页 (index.html)"""
    
    recent_posts = parsed_posts[:config.MAX_POSTS_ON_INDEX]

    # 构造文章列表 HTML
    posts_list_html = []
    for post in recent_posts:
        link = make_internal_url(os.path.join(config.POSTS_DIR, f"{post['slug']}.html"))
        date_str = post['date'].strftime('%Y-%m-%d')
        
        tags_html = "".join([
            f'<a href="{config.SITE_ROOT}/tags/{tag["slug"]}.html" class="tag-badge">{tag["name"]}</a>'
            for tag in post.get('tags', [])
        ])

        item = f"""
            <div class="post-card">
                <h2 class="post-card-title"><a href="{link}">{post['title']}</a></h2>
                <div class="post-card-meta">
                    <span class="meta-date">{date_str}</span>
                    <div class="meta-tags">{tags_html}</div>
                </div>
                <div class="post-card-excerpt">
                    {post.get('description', '暂无摘要')}
                </div>
            </div>
        """
        posts_list_html.append(item)
    
    output_path = os.path.join(config.BUILD_DIR, config.INDEX_FILE)
    canonical_url = make_internal_url('/')
    
    main_title_html = f"<h1>{config.BLOG_TITLE}</h1>"
    content_html = "<div class='posts-list'>" + "".join(posts_list_html) + "</div>"
    
    regenerate_html_file(
        output_path=output_path,
        page_id='index',
        page_title=generate_page_title('index'),
        canonical_url=canonical_url,
        current_year=datetime.now().year,
        site_root=config.SITE_ROOT,
        blog_title=config.BLOG_TITLE,
        blog_description=config.BLOG_DESCRIPTION,
        blog_author=config.BLOG_AUTHOR,
        main_title_html=main_title_html,
        content_html=content_html,
        footer_time_info=f"总文章数: {len(parsed_posts)} | " + datetime.now(timezone.utc).strftime('页面生成于 %Y-%m-%d %H:%M:%S UTC'),
    )


def generate_archive_html(parsed_posts: List[Dict[str, Any]]):
    """生成归档页 (archive.html)"""
    
    archive_map = defaultdict(list)
    for post in parsed_posts:
        year = post['date'].year
        archive_map[year].append(post)
        
    archive_html = []
    for year in sorted(archive_map.keys(), reverse=True):
        year_html = f"<h2>{year}</h2><ul class='archive-list'>"
        for post in archive_map[year]:
            link = make_internal_url(os.path.join(config.POSTS_DIR, f"{post['slug']}.html"))
            date_str = post['date'].strftime('%m-%d')
            item = f"<li><span class='archive-date'>[{date_str}]</span> <a href='{link}'>{post['title']}</a></li>"
            year_html += item
        year_html += "</ul>"
        archive_html.append(year_html)

    output_path = os.path.join(config.BUILD_DIR, config.ARCHIVE_FILE)
    canonical_url = make_internal_url(config.ARCHIVE_FILE)
    
    main_title_html = "<h1>文章归档</h1>"
    content_html = "<div class='archive-wrapper'>" + "".join(archive_html) + "</div>"
    
    regenerate_html_file(
        output_path=output_path,
        page_id='archive',
        page_title=generate_page_title('archive'),
        canonical_url=canonical_url,
        current_year=datetime.now().year,
        site_root=config.SITE_ROOT,
        blog_title=config.BLOG_TITLE,
        blog_description=config.BLOG_DESCRIPTION,
        blog_author=config.BLOG_AUTHOR,
        main_title_html=main_title_html,
        content_html=content_html,
    )


def generate_tags_list_html(tag_map: Dict[str, List[Dict[str, Any]]]):
    """生成标签列表页 (tags.html)"""
    
    tags_list_html = []
    tag_counts = {slug: len(posts) for slug, posts in tag_map.items()}
    
    for slug in sorted(tag_map.keys()):
        count = tag_counts[slug]
        tag_name = tag_map[slug][0]['tags'][0]['name'] if tag_map[slug] else slug
        link = make_internal_url(os.path.join(config.TAGS_DIR, f"{slug}.html"))
        item = f"""
            <li>
                <a href="{link}" class="tag-link-block">
                    <span class="tag-name">{tag_name}</span> 
                    <span class="tag-count">({count} 篇)</span>
                </a>
            </li>
        """
        tags_list_html.append(item)

    output_path = os.path.join(config.BUILD_DIR, config.TAGS_FILE)
    canonical_url = make_internal_url(config.TAGS_FILE)
    
    main_title_html = "<h1>标签列表</h1>"
    content_html = f"<ul class='tags-cloud-list'>{''.join(tags_list_html)}</ul>"
    
    regenerate_html_file(
        output_path=output_path,
        page_id='tags',
        page_title=generate_page_title('tags'),
        canonical_url=canonical_url,
        current_year=datetime.now().year,
        site_root=config.SITE_ROOT,
        blog_title=config.BLOG_TITLE,
        blog_description=config.BLOG_DESCRIPTION,
        blog_author=config.BLOG_AUTHOR,
        main_title_html=main_title_html,
        content_html=content_html,
    )


def generate_tag_page(tag_slug: str, posts: List[Dict[str, Any]]):
    """生成单个标签页面的 HTML"""
    
    tag_name = posts[0]['tags'][0]['name'] if posts else tag_slug
    internal_path = os.path.join(config.TAGS_DIR, f'{tag_slug}.html')
    output_path = os.path.join(config.BUILD_DIR, internal_path)
    canonical_url = make_internal_url(internal_path)
    
    posts_list_html = []
    for post in posts:
        link = make_internal_url(os.path.join(config.POSTS_DIR, f"{post['slug']}.html"))
        date_str = post['date'].strftime('%Y-%m-%d')
        
        tags_html = "".join([
            f'<a href="{config.SITE_ROOT}/tags/{tag["slug"]}.html" class="tag-badge">{tag["name"]}</a>'
            for tag in post.get('tags', []) if tag['slug'] != tag_slug
        ])
        if tags_html:
            tags_html = "其他标签: " + tags_html
        
        item = f"""
            <div class="post-card">
                <h2 class="post-card-title"><a href="{link}">{post['title']}</a></h2>
                <div class="post-card-meta">
                    <span class="meta-date">{date_str}</span>
                    <div class="meta-tags">{tags_html}</div>
                </div>
                <div class="post-card-excerpt">
                    {post.get('description', '暂无摘要')}
                </div>
            </div>
        """
        posts_list_html.append(item)

    main_title_html = f"<h1>标签: {tag_name} ({len(posts)} 篇)</h1>"
    content_html = "<div class='posts-list'>" + "".join(posts_list_html) + "</div>"

    regenerate_html_file(
        output_path=output_path,
        page_id='tag-page',
        page_title=generate_page_title('tag-page', tag_name),
        canonical_url=canonical_url,
        current_year=datetime.now().year,
        site_root=config.SITE_ROOT,
        blog_title=config.BLOG_TITLE,
        blog_description=config.BLOG_DESCRIPTION,
        blog_author=config.BLOG_AUTHOR,
        main_title_html=main_title_html,
        content_html=content_html,
    )


def generate_about_html(post_data: Dict[str, Any]):
    """生成关于页面 (about.html)"""
    
    output_path = os.path.join(config.BUILD_DIR, config.ABOUT_FILE)
    canonical_url = make_internal_url(config.ABOUT_FILE)
    main_title_html = f"<h1>{post_data['title']}</h1>"
    
    regenerate_html_file(
        output_path=output_path,
        page_id='about',
        page_title=generate_page_title('about'),
        canonical_url=canonical_url,
        current_year=datetime.now().year,
        site_root=config.SITE_ROOT,
        blog_title=config.BLOG_TITLE,
        blog_description=config.BLOG_DESCRIPTION,
        blog_author=config.BLOG_AUTHOR,
        main_title_html=main_title_html,
        content_html=post_data['content_html'],
        toc_html=post_data.get('toc_html', '') 
    )


def generate_robots_txt():
    """生成 robots.txt 文件"""
    robots_content = f"""# robots.txt
User-agent: *
Allow: /
Sitemap: {make_internal_url(config.SITEMAP_FILE)}
"""
    try:
        output_path = os.path.join(config.BUILD_DIR, 'robots.txt')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(robots_content)
        print(f"SUCCESS: Generated robots.txt.")
    except Exception as e:
        print(f"Error generating robots.txt: {e}")

def generate_sitemap(parsed_posts: List[Dict[str, Any]]) -> str:
    """生成 sitemap.xml 内容"""
    
    urls = []
    base_url_normalized = config.BASE_URL.rstrip('/')
    
    # 1. 首页
    urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url('/')}</loc>
        <lastmod>{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')}</lastmod>
        <changefreq>daily</changefreq>
        <priority>1.0</priority>
    </url>""")
    
    # 2. 通用页面
    for page in [config.ARCHIVE_FILE, config.TAGS_FILE, config.ABOUT_FILE]:
        urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url(page)}</loc>
        <lastmod>{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>
    </url>""")

    # 3. 文章详情页
    for post in parsed_posts:
        internal_path = os.path.join(config.POSTS_DIR, f"{post['slug']}.html")
        loc = f"{base_url_normalized}{make_internal_url(internal_path)}"
        # 使用文章本身的日期作为 lastmod
        lastmod = post['date'].strftime('%Y-%m-%dT%H:%M:%S+00:00') 
        urls.append(f"""
    <url>
        <loc>{loc}</loc>
        <lastmod>{lastmod}</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.7</priority>
    </url>""")
    
    sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{"".join(urls)}
</urlset>"""
    return sitemap_content

def generate_rss(parsed_posts: List[Dict[str, Any]]) -> str:
    """生成 rss.xml 内容"""
    
    items = []
    base_url_normalized = config.BASE_URL.rstrip('/')
    
    # 仅取最新的10篇
    for post in parsed_posts[:10]:
        # 修复文章链接
        link = f"{base_url_normalized}{make_internal_url(os.path.join(config.POSTS_DIR, f"{post['slug']}.html"))}"
        pub_date = post['date'].strftime('%a, %d %b %Y %H:%M:%S +0000') # RFC 822 格式
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
    <language>zh-Hans</language>
    <pubDate>{datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>
    <lastBuildDate>{datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>
    <managingEditor>{config.BLOG_AUTHOR}</managingEditor>
    <webMaster>{config.BLOG_AUTHOR}</webMaster>
    <generator>Simple Blog Generator</generator>
{"".join(items)}
</channel>
</rss>"""
    return rss_content
