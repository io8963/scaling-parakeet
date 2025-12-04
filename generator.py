# generator.py

import os
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Dict, Any
from jinja2 import Environment, FileSystemLoader
import json # NEW: 导入 json 库用于生成 JSON-LD

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
    
    # 否则，返回 SITE_ROOT + 路径
    if not path_without_leading_slash:
        return site_root
    return site_root + '/' + path_without_leading_slash

def create_base_context(page_id: str, title: str, description: str = config.BLOG_DESCRIPTION, url_path: str = '/') -> Dict[str, Any]:
    """创建所有页面共享的基本上下文。"""
    
    # 修复：确保所有页面都有正确的 canonical_url
    if url_path == '/':
        canonical_url_path = make_internal_url('/')
    else:
        canonical_url_path = make_internal_url(url_path)
    
    return {
        'page_id': page_id,
        'blog_title': config.BLOG_TITLE,
        'blog_description': description,
        'blog_author': config.BLOG_AUTHOR,
        'site_root': get_site_root(),
        'current_year': datetime.now(timezone.utc).year,
        'lang': 'zh-CN',
        'css_filename': config.CSS_FILENAME, # 传递带哈希的 CSS 文件名
        'page_title': title,
        'canonical_url': config.BASE_URL.rstrip('/') + canonical_url_path,
        'footer_time_info': f"Build time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
    }

# --- 核心页面生成函数 ---

def generate_index_html(parsed_posts: List[Dict[str, Any]]):
    """生成首页 index.html。"""
    template = env.get_template('base.html')
    
    # 首页只显示 MAX_POSTS_ON_INDEX 数量的文章
    posts_for_index = parsed_posts[:config.MAX_POSTS_ON_INDEX]
    
    # 准备上下文
    context = create_base_context(
        page_id='index', 
        title='首页', 
        url_path='/'
    )
    
    # 关键修正：为首页和归档页传递 posts 列表，并将列表渲染逻辑移到 base.html
    context['main_title_html'] = f"<h1>{config.BLOG_TITLE}</h1><p>{config.BLOG_DESCRIPTION}</p>"
    context['content_html'] = "" # 列表内容现在由 base.html 中的 posts 循环渲染
    context['posts'] = posts_for_index
    context['max_posts_on_index'] = config.MAX_POSTS_ON_INDEX # 传递用于判断“查看更多”的变量
    context['toc_html'] = ""
    context['json_ld_schema'] = create_index_json_ld() # 首页的 JSON-LD
    
    # 渲染并写入文件
    try:
        html_content = template.render(context)
        output_path = os.path.join(config.BUILD_DIR, 'index.html')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"SUCCESS: Generated index.html with {len(posts_for_index)} posts.")
    except Exception as e:
        print(f"Error generating index.html: {type(e).__name__}: {e}")

def generate_archive_html(parsed_posts: List[Dict[str, Any]]):
    """生成归档页 archive.html (显示所有文章)。"""
    template = env.get_template('base.html')

    # 准备上下文
    context = create_base_context(
        page_id='archive', 
        title='文章归档', 
        url_path='/archive.html'
    )
    
    # 关键修正：为首页和归档页传递 posts 列表，并将列表渲染逻辑移到 base.html
    context['main_title_html'] = "<h1>文章归档</h1>"
    context['content_html'] = "" # 列表内容现在由 base.html 中的 posts 循环渲染
    context['posts'] = parsed_posts # 归档页显示所有文章
    context['toc_html'] = ""

    # 渲染并写入文件
    try:
        html_content = template.render(context)
        output_path = os.path.join(config.BUILD_DIR, 'archive.html')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"SUCCESS: Generated archive.html with {len(parsed_posts)} posts.")
    except Exception as e:
        print(f"Error generating archive.html: {type(e).__name__}: {e}")


def generate_post_html(post: Dict[str, Any]):
    """生成单篇文章页。"""
    template = env.get_template('base.html')
    
    # 准备上下文
    context = create_base_context(
        page_id='post', 
        title=post['title'], 
        description=post['excerpt'],
        url_path=f"/{post['link']}" # 确保 URL 正确，例如 /posts/slug.html
    )
    
    context['main_title_html'] = f"<h1>{post['title']}</h1>"
    context['content_html'] = post['content_html'] # 文章内容
    context['toc_html'] = post['toc_html'] # 目录内容
    context['post_date'] = post['date_formatted_full'] # 完整格式的日期
    context['post_tags'] = post.get('tags', []) # 标签列表
    context['json_ld_schema'] = create_article_json_ld(post) # 文章的 JSON-LD

    # 渲染并写入文件
    try:
        output_path = os.path.join(config.POSTS_OUTPUT_DIR, f"{post['slug']}.html")
        os.makedirs(os.path.dirname(output_path), exist_ok=True) # 确保目录存在
        html_content = template.render(context)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"SUCCESS: Generated post page for '{post['slug']}'")
    except Exception as e:
        print(f"Error generating post page for '{post['slug']}': {type(e).__name__}: {e}")


def generate_tags_list_html(tag_map: Dict[str, List[Dict[str, Any]]]):
    """生成所有标签的列表页 tags.html。"""
    template = env.get_template('base.html')
    
    # 准备上下文
    context = create_base_context(
        page_id='tags', 
        title='所有标签', 
        url_path='/tags.html'
    )
    
    tag_list_html = "<h1>所有标签</h1>"
    tag_list_html += "<div class='tag-cloud'>"
    
    # 排序标签，按文章数量降序
    sorted_tags = sorted(tag_map.items(), key=lambda item: len(item[1]), reverse=True)
    
    for tag_name, posts in sorted_tags:
        tag_slug = posts[0]['tags'][0]['slug'] # 假设第一个文章的标签 slug 是正确的
        count = len(posts)
        tag_list_html += f"<a href=\"{make_internal_url(os.path.join(config.TAGS_DIR, tag_slug + '.html'))}\" class=\"tag-badge\">{tag_name} ({count})</a>"
        
    tag_list_html += "</div>"
    
    context['main_title_html'] = ""
    context['content_html'] = tag_list_html # 标签列表内容
    context['toc_html'] = ""

    # 渲染并写入文件
    try:
        html_content = template.render(context)
        output_path = os.path.join(config.BUILD_DIR, 'tags.html')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"SUCCESS: Generated tags.html with {len(tag_map)} tags.")
    except Exception as e:
        print(f"Error generating tags.html: {type(e).__name__}: {e}")

def generate_tag_page(tag_name: str, posts: List[Dict[str, Any]]):
    """为单个标签生成页面 /tags/{tag_slug}.html。"""
    template = env.get_template('base.html')
    tag_slug = posts[0]['tags'][0]['slug']
    
    # 准备上下文
    context = create_base_context(
        page_id='tag', 
        title=f"标签: {tag_name}", 
        url_path=f"/tags/{tag_slug}.html"
    )

    # 关键修正：为标签页传递 posts 列表，并将列表渲染逻辑移到 base.html
    context['main_title_html'] = f"<h1>标签: {tag_name}</h1><p>共 {len(posts)} 篇文章</p>"
    context['content_html'] = "" # 列表内容现在由 base.html 中的 posts 循环渲染
    context['posts'] = posts
    context['toc_html'] = ""

    # 渲染并写入文件
    try:
        output_path = os.path.join(config.TAGS_OUTPUT_DIR, f"{tag_slug}.html")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        html_content = template.render(context)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"SUCCESS: Generated tag page for '{tag_name}' ({tag_slug}).")
    except Exception as e:
        print(f"Error generating tag page for '{tag_name}': {type(e).__name__}: {e}")


# --- 静态和 XML 文件生成函数 (省略大部分，仅保留 JSON-LD 辅助) ---

def create_index_json_ld() -> str:
    """生成首页的 Organization JSON-LD 结构化数据。"""
    schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": config.BLOG_TITLE,
        "url": config.BASE_URL,
        "description": config.BLOG_DESCRIPTION,
        "author": {
            "@type": "Person",
            "name": config.BLOG_AUTHOR
        }
    }
    return json.dumps(schema, indent=2, ensure_ascii=False)

def create_article_json_ld(post: Dict[str, Any]) -> str:
    """生成单篇文章的 Article JSON-LD 结构化数据。"""
    # 假设 post['link'] 是 posts/slug.html
    link = f"{config.BASE_URL.rstrip('/')}/{post['link']}"
    
    # 确保日期格式为 ISO 8601
    date_published = post['date'].isoformat()
    date_modified = post.get('date_modified', post['date']).isoformat()

    schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post['title'],
        "url": link,
        "description": post['excerpt'],
        "datePublished": date_published,
        "dateModified": date_modified,
        "author": {
            "@type": "Person",
            "name": config.BLOG_AUTHOR
        },
        "publisher": {
            "@type": "Organization",
            "name": config.BLOG_TITLE,
            "url": config.BASE_URL
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": config.BASE_URL
        }
    }
    return json.dumps(schema, indent=2, ensure_ascii=False)
    
# 省略 generate_robots_txt, generate_sitemap, generate_rss 等函数
# 这些函数依赖于 config.py 中定义的常量，且未直接影响内容显示问题
# 在实际项目中应保留，此处为避免截断，仅保留核心渲染逻辑。
# ... (generate_sitemap, generate_rss) ...

def generate_robots_txt():
    """生成 robots.txt 文件。"""
    content = f"User-agent: *\nAllow: /\n\nSitemap: {config.BASE_URL.rstrip('/')}{make_internal_url(config.SITEMAP_FILE)}\n"
    try:
        output_path = os.path.join(config.BUILD_DIR, config.ROBOTS_FILE)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"SUCCESS: Generated {config.ROBOTS_FILE}.")
    except Exception as e:
        print(f"Error generating robots.txt: {type(e).__name__}: {e}")

def generate_sitemap(parsed_posts: List[Dict[str, Any]]) -> str:
    """生成 sitemap.xml 内容"""
    
    url_tags = []
    base_url_normalized = config.BASE_URL.rstrip('/')
    
    # 首页
    url_tags.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url('/')}</loc>
        <changefreq>daily</changefreq>
        <priority>1.0</priority>
    </url>""")
    
    # 归档页
    url_tags.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url('/archive.html')}</loc>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>
    </url>""")

    # 标签页列表
    url_tags.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url('/tags.html')}</loc>
        <changefreq>weekly</changefreq>
        <priority>0.7</priority>
    </url>""")
    
    # 单篇文章
    for post in parsed_posts:
        last_mod = post['date'].strftime('%Y-%m-%d')
        url_tags.append(f"""
    <url>
        <loc>{base_url_normalized}{make_internal_url(post['link'])}</loc>
        <lastmod>{last_mod}</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.6</priority>
    </url>""")

    sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{ "".join(url_tags) }
</urlset>"""

    return sitemap_content

def generate_rss(parsed_posts: List[Dict[str, Any]]) -> str:
    """生成 rss.xml 内容"""
    
    items = []
    base_url_normalized = config.BASE_URL.rstrip('/')
    
    # 仅取最新的10篇
    for post in parsed_posts[:10]:
        # 修复文章链接
        link = f"{base_url_normalized}{make_internal_url(post['link'])}"
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
    <language>zh-cn</language>
    <lastBuildDate>{datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>
    <managingEditor>{config.BLOG_AUTHOR}</managingEditor>
    <webMaster>{config.BLOG_AUTHOR}</webMaster>{ "".join(items) }
</channel>
</rss>"""

    return rss_content
