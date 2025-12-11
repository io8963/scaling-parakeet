# parser.py - 调试增强版

import os
import re
import yaml
import markdown
from datetime import datetime, date
from typing import Dict, Any, Tuple
import config 
import unicodedata 
from bs4 import BeautifulSoup 

def standardize_date(dt_obj: Any) -> date:
    if isinstance(dt_obj, datetime):
        return dt_obj.date()
    elif isinstance(dt_obj, date):
        return dt_obj
    return date.today() 

def my_custom_slugify(s: str, separator: str) -> str:
    s = str(s).lower().strip()
    s = unicodedata.normalize('NFKD', s)
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s-]+', separator, s).strip(separator)
    return s

def tag_to_slug(tag_name: str) -> str:
    slug = tag_name.lower()
    slug = unicodedata.normalize('NFKD', slug)
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug).strip('-')
    return slug

# -------------------------------------------------------------------------
# 【核心逻辑：代码块后处理】(带调试打印)
# -------------------------------------------------------------------------
def post_process_html(html_content: str, filename: str = "unknown") -> str:
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
    lang_map = {
        'py': 'PYTHON', 'python': 'PYTHON',
        'js': 'JS', 'javascript': 'JS', 'typescript': 'TS', 'ts': 'TS',
        'sh': 'SHELL', 'bash': 'SHELL', 'shell': 'SHELL', 'zsh': 'SHELL',
        'html': 'HTML', 'css': 'CSS', 'scss': 'CSS',
        'json': 'JSON', 'sql': 'SQL', 'yaml': 'YAML', 'yml': 'YAML',
        'md': 'MARKDOWN', 'markdown': 'MARKDOWN',
        'c': 'C', 'cpp': 'C++', 'go': 'GO', 'java': 'JAVA', 'rust': 'RUST'
    }

    # 查找所有高亮容器
    # 注意：pymdownx 生成的可能是 div.highlight 或 pre.highlight
    code_blocks = soup.find_all(class_='highlight')
    
    for block in code_blocks:
        lang = None
        found_class = ""
        
        # 策略 A: 检查容器本身的 class
        classes = block.get('class', [])
        for cls in classes:
            clean_cls = cls.replace('language-', '')
            if clean_cls in lang_map:
                lang = lang_map[clean_cls]
                found_class = cls
                break
        
        # 策略 B: 如果容器没找到，检查内部 code 标签
        if not lang:
            code_tag = block.find('code')
            if code_tag:
                code_classes = code_tag.get('class', [])
                for cls in code_classes:
                    clean_cls = cls.replace('language-', '')
                    if clean_cls in lang_map:
                        lang = lang_map[clean_cls]
                        found_class = cls
                        break
        
        # 写入属性
        target_pre = block if block.name == 'pre' else block.find('pre')
        
        if target_pre:
            if lang:
                target_pre['data-lang'] = lang
                # --- 调试打印 (如果在终端看到这个，说明 HTML 生成成功了) ---
                print(f"      [DEBUG] Injected data-lang='{lang}' (found class: {found_class})")
            else:
                # 默认设为 CODE，方便 CSS 统一处理
                target_pre['data-lang'] = 'CODE'

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
    
    metadata['tags'] = [{'name': t, 'slug': tag_to_slug(t)} for t in tags_list if t]

    if 'slug' not in metadata:
        base_name = os.path.splitext(os.path.basename(md_file_path))[0]
        # 简单的 slug 生成逻辑
        metadata['slug'] = base_name.lower()
    
    if 'title' not in metadata:
        metadata['title'] = metadata['slug']
    
    metadata['excerpt'] = metadata.get('summary') or ''
    
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
    
    # 传递文件名用于调试
    content_html = post_process_html(raw_html, filename=os.path.basename(md_file_path))
    
    toc_html = md.toc if hasattr(md, 'toc') else ""

    return metadata, content_markdown, content_html, toc_html
