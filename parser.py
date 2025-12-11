# parser.py

import os
import re
import yaml
import markdown
from datetime import datetime, date
from typing import Dict, Any, Tuple
import config 
import unicodedata 
from bs4 import BeautifulSoup 

# 辅助函数 - 将日期时间对象标准化为日期对象
def standardize_date(dt_obj: Any) -> date:
    if isinstance(dt_obj, datetime):
        return dt_obj.date()
    elif isinstance(dt_obj, date):
        return dt_obj
    return date.today() 

# -------------------------------------------------------------------------
# 【TOC/目录专用 Slugify】
# -------------------------------------------------------------------------
def my_custom_slugify(s: str, separator: str) -> str:
    s = str(s).lower().strip()
    s = unicodedata.normalize('NFKD', s)
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s-]+', separator, s).strip(separator)
    return s

# -------------------------------------------------------------------------
# 【标签/Tag 专用 Slugify】
# -------------------------------------------------------------------------
def tag_to_slug(tag_name: str) -> str:
    slug = tag_name.lower()
    slug = unicodedata.normalize('NFKD', slug)
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug).strip('-')
    return slug

# -------------------------------------------------------------------------
# 【核心逻辑：代码块后处理】(修复语言显示问题的关键)
# -------------------------------------------------------------------------
def post_process_html(html_content: str) -> str:
    """
    使用 BeautifulSoup 对 HTML 进行后处理：
    1. 图片懒加载
    2. 表格包裹
    3. [关键] 代码块语言标签注入
    """
    if not html_content:
        return ""
        
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. 图片懒加载
    for img in soup.find_all('img'):
        if not img.get('loading'):
            img['loading'] = 'lazy'

    # 2. 表格包裹器
    for table in soup.find_all('table'):
        parent = table.parent
        if parent and 'table-wrapper' not in parent.get('class', []):
            wrapper_div = soup.new_tag('div', class_='table-wrapper')
            table.replace_with(wrapper_div)
            wrapper_div.append(table)

    # 3. [关键修复] 代码块语言识别
    # 查找所有由 pymdownx 生成的高亮容器 div.highlight
    for div in soup.find_all('div', class_='highlight'):
        # 获取 div 的类列表 (例如 ['highlight', 'python'])
        classes = div.get('class', [])
        lang = 'CODE' # 默认值
        
        # 寻找语言类名 (忽略 'highlight')
        for cls in classes:
            if cls != 'highlight':
                # 找到语言了！(例如 python, js, html)
                # 进行简单的标准化映射
                lang_map = {
                    'py': 'PYTHON', 'python': 'PYTHON',
                    'js': 'JS', 'javascript': 'JS',
                    'ts': 'TS', 'typescript': 'TS',
                    'sh': 'SHELL', 'bash': 'SHELL', 'shell': 'SHELL', 'zsh': 'SHELL',
                    'html': 'HTML', 'css': 'CSS', 'scss': 'CSS',
                    'json': 'JSON', 'sql': 'SQL', 'yaml': 'YAML', 'yml': 'YAML',
                    'md': 'MARKDOWN', 'markdown': 'MARKDOWN',
                    'c': 'C', 'cpp': 'C++', 'c++': 'C++',
                    'go': 'GO', 'java': 'JAVA', 'rust': 'RUST'
                }
                lang = lang_map.get(cls.lower(), cls.upper())
                break
        
        # 找到 div 内部的 pre 标签
        pre = div.find('pre')
        if pre:
            # 将识别到的语言写入 pre 的 data-lang 属性
            # CSS 将使用 attr(data-lang) 直接读取这个值
            pre['data-lang'] = lang

    return str(soup)


def get_metadata_and_content(md_file_path: str) -> Tuple[Dict[str, Any], str, str, str]:
    try:
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file {md_file_path}: {e}")
        return {}, "", "", ""

    match = re.match(r'---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)

    if match:
        yaml_data = match.group(1)
        content_markdown = content[len(match.group(0)):]
        try:
            metadata = yaml.safe_load(yaml_data) or {}
        except yaml.YAMLError as exc:
            print(f"Error parsing YAML frontmatter in {md_file_path}: {exc}")
            metadata = {}
    else:
        metadata = {}
        content_markdown = content

    # 元数据处理
    raw_date = metadata.get('date')
    if raw_date:
        metadata['date'] = standardize_date(raw_date)
        metadata['date_formatted'] = metadata['date'].strftime('%Y-%m-%d')
    else:
        metadata['date'] = date.today()
        metadata['date_formatted'] = metadata['date'].strftime('%Y-%m-%d')
        
    tags_list = metadata.get('tags', [])
    if isinstance(tags_list, str):
        tags_list = [t.strip() for t in tags_list.split(',')]
    
    metadata['tags'] = [
        {'name': t, 'slug': tag_to_slug(t)} 
        for t in tags_list if t
    ]

    if 'slug' not in metadata:
        file_name = os.path.basename(md_file_path)
        base_name = os.path.splitext(file_name)[0]
        slug_match = re.match(r'^(\d{4}-\d{2}-\d{2}-)?(.*)$', base_name)
        if slug_match and slug_match.group(2):
            metadata['slug'] = slug_match.group(2).lower()
        else:
            metadata['slug'] = base_name.lower()
    
    if 'title' not in metadata:
        metadata['title'] = metadata['slug'].replace('-', ' ').title()
        if not metadata['title'] and content_markdown:
             metadata['title'] = content_markdown.split('\n', 1)[0].strip()
    
    metadata['excerpt'] = metadata.get('summary') or metadata.get('excerpt') or metadata.get('description') or ''
    
    # Markdown 渲染
    extension_configs = config.MARKDOWN_EXTENSION_CONFIGS.copy()
    if 'toc' in extension_configs:
        extension_configs['toc']['slugify'] = my_custom_slugify
    
    md = markdown.Markdown(
        extensions=config.MARKDOWN_EXTENSIONS, 
        extension_configs=extension_configs, 
        output_format='html5',
    )
    
    raw_html = md.convert(content_markdown)
    
    # --- 调用后处理函数 ---
    content_html = post_process_html(raw_html)
    
    toc_html = md.toc if hasattr(md, 'toc') else ""

    return metadata, content_markdown, content_html, toc_html
