
# parser.py

import os
import re
import yaml
import markdown
from datetime import datetime, date
from typing import Dict, Any, Tuple
import config 

# NEW: 辅助函数 - 将日期时间对象标准化为日期对象
def standardize_date(dt_obj: Any) -> date:
    """将 datetime 或 date 对象标准化为 date 对象。"""
    if isinstance(dt_obj, datetime):
        return dt_obj.date()
    elif isinstance(dt_obj, date):
        return dt_obj
    return date.today() 

# NEW: 辅助函数 - 针对中文的 slugify
def my_custom_slugify(s, separator):
    """一个简单的中文友好的 slugify 函数"""
    s = str(s).lower().strip()
    s = re.sub(r'[\s]+', separator, s) 
    s = re.sub(r'[^\w\s-]', '', s) 
    return s.strip(separator)

def tag_to_slug(tag_name: str) -> str:
    """
    [关键修复] 将标签名转换为 URL 友好的 slug。
    使用更强的正则替换逻辑，移除所有非字母数字和非横线字符。
    """
    # 1. 小写
    slug = tag_name.lower()
    # 2. 将非字母数字、非横线、非空格的字符替换为空
    # 保留中文的\u4e00-\u9fa5
    slug = re.sub(r'[^\w\s\u4e00-\u9fa5-]', '', slug) 
    # 3. 将空格和多个横线替换为单个横线，并移除首尾横线
    slug = re.sub(r'[\s-]+', '-', slug).strip('-')
    return slug

def get_metadata_and_content(md_file_path: str) -> Tuple[Dict[str, Any], str, str, str]:
    """
    从 Markdown 文件中读取 Frontmatter 元数据和内容。
    返回: (metadata, content_markdown, content_html, toc_html)
    """
    try:
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file {md_file_path}: {e}")
        return {}, "", "", ""

    # 分隔 Frontmatter 和内容
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

    
    # --- 元数据处理 ---
    
    # 1. date
    raw_date = metadata.get('date')
    if raw_date:
        metadata['date'] = standardize_date(raw_date)
        metadata['date_formatted'] = metadata['date'].strftime('%Y-%m-%d')
    else:
        metadata['date'] = date.today()
        metadata['date_formatted'] = metadata['date'].strftime('%Y-%m-%d')
        
    # 2. tags
    tags_list = metadata.get('tags', [])
    if isinstance(tags_list, str):
        tags_list = [t.strip() for t in tags_list.split(',')]
    
    metadata['tags'] = [
        {'name': t, 'slug': tag_to_slug(t)} 
        for t in tags_list if t
    ]

    # 3. slug
    if 'slug' not in metadata:
        file_name = os.path.basename(md_file_path)
        base_name = os.path.splitext(file_name)[0]
        slug_match = re.match(r'^(\d{4}-\d{2}-\d{2}-)?(.*)$', base_name)
        if slug_match and slug_match.group(2):
            metadata['slug'] = slug_match.group(2).lower()
        else:
            metadata['slug'] = base_name.lower()
    
    # 4. title
    if 'title' not in metadata:
        metadata['title'] = metadata['slug'].replace('-', ' ').title()
        if not metadata['title'] and content_markdown:
             metadata['title'] = content_markdown.split('\n', 1)[0].strip()
    
    # 5. summary/excerpt (保留摘要功能)
    metadata['excerpt'] = metadata.get('summary') or metadata.get('excerpt') or metadata.get('description') or ''
    
    # --- Markdown 渲染 ---
    
    # 1. 准备配置
    extension_configs = config.MARKDOWN_EXTENSION_CONFIGS.copy()
    
    # 动态注入 slugify 函数
    if 'toc' in extension_configs:
        extension_configs['toc']['slugify'] = my_custom_slugify
    elif 'markdown.extensions.toc' in extension_configs:
        extension_configs['markdown.extensions.toc']['slugify'] = my_custom_slugify
    
    md = markdown.Markdown(
        extensions=config.MARKDOWN_EXTENSIONS, 
        extension_configs=extension_configs, 
        output_format='html5',
    )
    
    # 2. 转换
    content_html = md.convert(content_markdown)
    
    # -------------------------------------------------------------------------
    # [新增] UI 增强：图片懒加载 (Lazy Load)
    # 为所有 <img> 标签强制添加 loading="lazy" 属性
    # -------------------------------------------------------------------------
    if '<img' in content_html:
        # 使用正则表达式匹配 img 标签，并确保不重复添加 loading 属性
        content_html = re.sub(
            r'<img(?![^>]*loading=["\'][^"\']*["\'])',
            r'<img loading="lazy"',
            content_html
        )

    # -------------------------------------------------------------------------
    # UI 增强：表格包裹器 (Table Wrapper)
    # 直接给 table 加上 wrapper div
    # -------------------------------------------------------------------------
    if '<table>' in content_html:
        # 避免在已经有 wrapper 的情况下重复添加（虽然 Markdown 不太可能生成）
        if '<div class="table-wrapper">' not in content_html:
            content_html = content_html.replace('<table>', '<div class="table-wrapper"><table>')
            content_html = content_html.replace('</table>', '</table></div>')
    
    # 3. 获取目录
    toc_html = md.toc if hasattr(md, 'toc') else ""

    return metadata, content_markdown, content_html, toc_html
