# parser.py (增强版：修复语言识别)

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
# 【核心逻辑：代码块后处理】(增强版)
# -------------------------------------------------------------------------
def post_process_html(html_content: str) -> str:
    """
    使用 BeautifulSoup 对 HTML 进行后处理：
    1. 图片懒加载
    2. 表格包裹
    3. [关键] 代码块语言标签注入 (同时检查 div 和 code)
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
    # 语言映射表
    lang_map = {
        'py': 'PYTHON', 'python': 'PYTHON',
        'js': 'JS', 'javascript': 'JS',
        'ts': 'TS', 'typescript': 'TS',
        'sh': 'SHELL', 'bash': 'SHELL', 'shell': 'SHELL', 'zsh': 'SHELL',
        'html': 'HTML', 'css': 'CSS', 'scss': 'CSS',
        'json': 'JSON', 'sql': 'SQL', 'yaml': 'YAML', 'yml': 'YAML',
        'md': 'MARKDOWN', 'markdown': 'MARKDOWN',
        'c': 'C', 'cpp': 'C++', 'c++': 'C++',
        'go': 'GO', 'java': 'JAVA', 'rust': 'RUST',
        'txt': 'TEXT', 'text': 'TEXT'
    }

    # 查找所有高亮容器
    for div in soup.find_all('div', class_='highlight'):
        lang = None
        
        # 策略 A: 检查 div 的 class (例如 highlight language-python)
        div_classes = div.get('class', [])
        for cls in div_classes:
            if cls.startswith('language-'):
                lang_key = cls.replace('language-', '')
                lang = lang_map.get(lang_key, lang_key.upper())
                break
            elif cls != 'highlight' and cls in lang_map: # 兼容旧格式
                lang = lang_map.get(cls, cls.upper())
                break
        
        # 策略 B: 如果 div 上没找到，检查内部的 code 标签
        if not lang:
            code_tag = div.find('code')
            if code_tag:
                code_classes = code_tag.get('class', [])
                for cls in code_classes:
                    if cls.startswith('language-'):
                        lang_key = cls.replace('language-', '')
                        lang = lang_map.get(lang_key, lang_key.upper())
                        break
        
        # 默认值
        if not lang:
            lang = 'CODE'

        # 找到 div 内部的 pre 标签并写入属性
        pre = div.find('pre')
        if pre:
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
