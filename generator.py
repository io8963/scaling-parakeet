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
    # 优化建议 3: 将标签固定为“构建于”
    time_label = "构建于" 
    build_time_utc_str = now_utc.strftime('%Y-%m-%d %H:%M:%S UTC') # 重命名变量
    footer_time_info_str = f"{time_label}: {build_time_utc_str}" 
    
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
        lang=config.LANG,
        main_title_html=main_title_html,
        content_html=post_data['content_html'],
        post_date=post_date_str,
        post_tags=post_data['tags'],
        footer_time_info=footer_time_info_str,
        toc_html=post_data['toc_html']
    )
    
def generate_index_html(parsed_posts: List[Dict[str, Any]]):
    """生成首页 HTML 文件"""
    
    index_posts = parsed_posts[:config.MAX_POSTS_ON_INDEX]
    
    content_html_parts = []
    
    # 构建文章列表 HTML
    content_html_parts.append("<ul class='post-list card'>")
    for post in index_posts:
        post_url = make_internal_url(os.path.join(config.POSTS_DIR, f"{post['slug']}.html"))
        post_date_str = post['date'].astimezone(timezone.utc).strftime('%Y-%m-%d')
        
        # 截取前 150 个字符作为摘要
        excerpt = post['content_markdown'][:150].split('\n')[0].strip() + '...'
        
        content_html_parts.append(f"""
        <li class='post-item'>
            <a href="{post_url}" class="post-title">{post['title']}</a>
            <p class="post-excerpt">{excerpt}</p>
            <span class="post-date">{post_date_str}</span>
        </li>
        """)
    content_html_parts.append("</ul>")
    
    # 添加归档链接
    if len(parsed_posts) > config.MAX_POSTS_ON_INDEX:
        archive_url = make_internal_url(config.ARCHIVE_FILE)
        content_html_parts.append(f"""
        <div class="card" style="text-align: center;">
            <a href="{archive_url}" class="button-primary">查看所有 {len(parsed_posts)} 篇文章 &raquo;</a>
        </div>
        """)
        
    content_html = '\n'.join(content_html_parts)
    
    regenerate_html_file(
        output_path=os.path.join(config.BUILD_DIR, config.INDEX_FILE),
        page_id='index',
        page_title=generate_page_title('index'),
        canonical_url=make_internal_url(config.INDEX_FILE),
        current_year=datetime.now().year,
        site_root=config.SITE_ROOT,
        blog_title=config.BLOG_TITLE,
        blog_description=config.BLOG_DESCRIPTION,
        blog_author=config.BLOG_AUTHOR,
        lang=config.LANG,
        main_title_html=f"<h1>{config.BLOG_TITLE}</h1>",
        content_html=content_html,
        # 页脚信息
        footer_time_info=f"总文章数: {len(parsed_posts)}"
    )

def generate_archive_html(parsed_posts: List[Dict[str, Any]]):
    """生成文章归档页 HTML 文件"""
    
    content_html_parts = []
    content_html_parts.append("<ul class='post-list card'>")
    
    for post in parsed_posts:
        post_url = make_internal_url(os.path.join(config.POSTS_DIR, f"{post['slug']}.html"))
        post_date_str = post['date'].astimezone(timezone.utc).strftime('%Y-%m-%d')
        
        content_html_parts.append(f"""
        <li class='post-item'>
            <a href="{post_url}" class="post-title">{post['title']}</a>
            <span class="post-date">{post_date_str}</span>
        </li>
        """)
        
    content_html_parts.append("</ul>")
    content_html = '\n'.join(content_html_parts)
    
    regenerate_html_file(
        output_path=os.path.join(config.BUILD_DIR, config.ARCHIVE_FILE),
        page_id='archive',
        page_title=generate_page_title('archive'),
        canonical_url=make_internal_url(config.ARCHIVE_FILE),
        current_year=datetime.now().year,
        site_root=config.SITE_ROOT,
        blog_title=config.BLOG_TITLE,
        blog_description=config.BLOG_DESCRIPTION,
        blog_author=config.BLOG_AUTHOR,
        lang=config.LANG,
        main_title_html="<h1>文章归档</h1>",
        content_html=content_html,
        # 页脚信息
        footer_time_info=f"总文章数: {len(parsed_posts)}"
    )
    
# 新增函数：生成关于页面 (about.html)
def generate_about_html(post_data: Dict[str, Any]):
    """生成关于页面 (about.html) 的 HTML 文件"""
    
    internal_path = config.ABOUT_FILE
    output_path = os.path.join(config.BUILD_DIR, internal_path)
    canonical_url = make_internal_url(internal_path)
    
    # 假设 about_post 包含 title 和 content_html
    main_title = post_data.get('title', '关于我') 
    main_title_html = f"<h1>{main_title}</h1>"
    
    # 页脚信息 (可以留空或自定义)
    footer_time_info_str = "保持简单，专注于内容"
    
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
        lang=config.LANG,
        main_title_html=main_title_html,
        content_html=post_data['content_html'],
        footer_time_info=footer_time_info_str,
        # 关于页面通常没有 TOC
        toc_html=''
    )

def generate_tags_list_html(tag_map: Dict[str, List[Dict[str, Any]]]):
    """生成所有标签的列表页 (tags.html)"""
    
    content_html_parts = []
    
    # 按标签名排序
    sorted_tags = sorted(tag_map.keys())
    
    content_html_parts.append("<div class='tags-cloud card'>")
    
    for tag_name in sorted_tags:
        posts = tag_map[tag_name]
        tag_slug = posts[0]['tags'][0]['slug'] # 从任意一篇文章中取出 slug
        count = len(posts)
        tag_url = make_internal_url(os.path.join(config.TAGS_DIR, f"{tag_slug}.html"))
        
        # 标签云样式：根据文章数量调整字体大小 (简单示例)
        font_size = max(1.0, min(2.0, 1.0 + count * 0.1)) # 1.0em 到 2.0em 之间
        
        content_html_parts.append(
            f'<a href="{tag_url}" class="tag-badge" style="font-size: {font_size}em; margin-right: 10px; margin-bottom: 10px;">{tag_name} ({count})</a>'
        )
        
    content_html_parts.append("</div>")
    content_html = '\n'.join(content_html_parts)
    
    regenerate_html_file(
        output_path=os.path.join(config.BUILD_DIR, config.TAGS_FILE),
        page_id='tags',
        page_title=generate_page_title('tags'),
        canonical_url=make_internal_url(config.TAGS_FILE),
        current_year=datetime.now().year,
        site_root=config.SITE_ROOT,
        blog_title=config.BLOG_TITLE,
        blog_description=config.BLOG_DESCRIPTION,
        blog_author=config.BLOG_AUTHOR,
        lang=config.LANG,
        main_title_html="<h1>所有标签</h1>",
        content_html=content_html,
        footer_time_info=f"总标签数: {len(tag_map)}"
    )

def generate_tag_page(tag_name: str, posts: List[Dict[str, Any]]):
    """为单个标签生成文章列表页"""
    
    tag_slug = posts[0]['tags'][0]['slug']
    internal_path = os.path.join(config.TAGS_DIR, f'{tag_slug}.html')
    output_path = os.path.join(config.BUILD_DIR, internal_path)
    canonical_url = make_internal_url(internal_path)
    
    content_html_parts = []
    content_html_parts.append("<ul class='post-list card'>")
    
    for post in posts:
        post_url = make_internal_url(os.path.join(config.POSTS_DIR, f"{post['slug']}.html"))
        post_date_str = post['date'].astimezone(timezone.utc).strftime('%Y-%m-%d')
        
        content_html_parts.append(f"""
        <li class='post-item'>
            <a href="{post_url}" class="post-title">{post['title']}</a>
            <span class="post-date">{post_date_str}</span>
        </li>
        """)
        
    content_html_parts.append("</ul>")
    content_html = '\n'.join(content_html_parts)
    
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
        lang=config.LANG,
        main_title_html=f"<h1>标签: {tag_name}</h1>",
        content_html=content_html,
        footer_time_info=f"此标签下有 {len(posts)} 篇文章"
    )

def generate_robots_txt() -> str:
    """生成 robots.txt 内容"""
    robots_txt_content = f"""User-agent: *
Allow: /

Sitemap: {get_site_root()}/sitemap.xml
"""
    try:
        output_path = os.path.join(config.BUILD_DIR, 'robots.txt')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(robots_txt_content)
        print("SUCCESS: Generated robots.txt.")
    except Exception as e:
        print(f"Error generating robots.txt: {e}")
        
    return robots_txt_content

def generate_sitemap(parsed_posts: List[Dict[str, Any]]) -> str:
    """生成 sitemap.xml 内容"""
    
    base_url_normalized = config.BASE_URL.rstrip('/')
    
    urls = []
    
    # 1. 首页
    urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url('/')}</loc>
        <changefreq>daily</changefreq>
        <priority>1.0</priority>
    </url>""")
    
    # 2. 其他静态页 (归档、标签列表、关于)
    for file_name in [config.ARCHIVE_FILE, config.TAGS_FILE, config.ABOUT_FILE]:
        urls.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url(file_name)}</loc>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>
    </url>""")
        
    # 3. 所有文章页
    all_tags = set()
    for post in parsed_posts:
        link = make_internal_url(os.path.join(config.POSTS_DIR, f"{post['slug']}.html"))
        # 使用文章的日期作为最后修改日期
        last_mod = post['date'].strftime('%Y-%m-%d')
        urls.append(f"""
    <url>
        <loc>{base_url_normalized}{link}</loc>
        <lastmod>{last_mod}</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.6</priority>
    </url>""")
        # 收集标签
        for tag_data in post.get('tags', []):
            all_tags.add(tag_data['slug'])
            
    # 4. 所有标签页
    for tag_slug in all_tags:
        link = make_internal_url(os.path.join(config.TAGS_DIR, f"{tag_slug}.html"))
        urls.append(f"""
    <url>
        <loc>{base_url_normalized}{link}</loc>
        <changefreq>monthly</changefreq>
        <priority>0.4</priority>
    </url>""")
        
    sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    {"\n".join(urls)}
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
    <language>{config.LANG.replace('-', '').lower()}</language>
    <lastBuildDate>{datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>
    <generator>Custom Python SSG</generator>
    {"\n".join(items)}
</channel>
</rss>"""

    return rss_content
