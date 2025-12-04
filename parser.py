# parser.py

import os
import re
import yaml
import markdown
from datetime import datetime, timezone, date
from typing import Dict, Any, Tuple
import config 
from markdown.extensions.toc import slugify as default_slugify # 导入默认的 slugify 函数

# NEW: 辅助函数 - 将日期时间对象标准化为日期对象
def standardize_date(dt_obj: Any) -> date:
    """将 datetime 或 date 对象标准化为 date 对象。"""
    if isinstance(dt_obj, datetime):
        return dt_obj.date()
    elif isinstance(dt_obj, date):
        return dt_obj
    # 如果是字符串或其他类型，则尝试解析（通常在 yaml.safe_load 中已经处理了）
    return date.today() 

# NEW: 辅助函数 - 针对中文的 slugify
def my_custom_slugify(s, separator):
    """一个简单的中文友好的 slugify 函数"""
    # 尽可能保持中文原样，只替换空格和特殊字符
    s = str(s).lower().strip()
    # 替换常见的标点符号为空格或连接符
    s = re.sub(r'[\s]+', separator, s) # 多个空格/空白符替换为 separator
    s = re.sub(r'[^\w\s-]', '', s) # 移除所有非单词字符 (包括中文)
    # 保持中文、数字、字母和连字符
    return s.strip(separator)

def tag_to_slug(tag_name: str) -> str:
    """将标签名转换为 URL 友好的 slug (小写，空格变'-')。"""
    return tag_name.lower().replace(' ', '-')

# 关键修正：新增 toc_html 的返回类型
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

    # 使用正则表达式分隔 Frontmatter (--- ... ---) 和内容
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
        # 如果没有 frontmatter，整个文件内容都是 markdown
        metadata = {}
        content_markdown = content

    
    # --- 元数据处理和标准化 ---
    
    # 1. 处理 date
    raw_date = metadata.get('date')
    if raw_date:
        metadata['date'] = standardize_date(raw_date)
        metadata['date_formatted'] = metadata['date'].strftime('%Y-%m-%d')
    else:
        # 如果没有日期，使用当前日期并发出警告
        metadata['date'] = date.today()
        metadata['date_formatted'] = metadata['date'].strftime('%Y-%m-%d')
        print(f"Warning: Missing 'date' in {md_file_path}. Using today's date.")
        
    # 2. 处理 tags
    tags_list = metadata.get('tags', [])
    if isinstance(tags_list, str):
        tags_list = [t.strip() for t in tags_list.split(',')]
        
    # 将标签转换为包含 name 和 slug 的字典列表
    metadata['tags'] = [
        {'name': t, 'slug': tag_to_slug(t)} 
        for t in tags_list
        if t # 过滤空字符串
    ]

    # 3. 处理 slug
    if 'slug' not in metadata:
        # 尝试从文件名生成 slug
        file_name = os.path.basename(md_file_path)
        base_name = os.path.splitext(file_name)[0]
        # 移除日期前缀，使用剩余部分作为 slug
        slug_match = re.match(r'^(\d{4}-\d{2}-\d{2}-)?(.*)$', base_name)
        if slug_match and slug_match.group(2):
            metadata['slug'] = slug_match.group(2).lower()
        else:
             # 如果文件名不是标准格式，使用整个文件名
            metadata['slug'] = base_name.lower()
    
    # 4. 处理 title
    if 'title' not in metadata:
        metadata['title'] = metadata['slug'].replace('-', ' ').title() # 简单的标题化
        if not metadata['title'] and content_markdown:
             # 从内容中获取第一行作为标题
             metadata['title'] = content_markdown.split('\n', 1)[0].strip()
    
    # 5. 处理 description/excerpt
    # 如果没有 description 或 excerpt，留空
    metadata['excerpt'] = metadata.get('excerpt', metadata.get('description', ''))
    
    # --- Markdown 渲染 ---
    
    # 1. 设置 Markdown 扩展 (注意：需要动态配置 slugify)
    
    # 复制配置，以便动态修改 TOC 的 slugify 
    extension_configs = config.MARKDOWN_EXTENSION_CONFIGS.copy()
    # 将自定义的 slugify 函数注入到 TOC 配置中
    extension_configs['markdown.extensions.toc']['slugify'] = my_custom_slugify
    
    md = markdown.Markdown(
        extensions=config.MARKDOWN_EXTENSIONS, 
        extension_configs=extension_configs, # 使用包含 slugify 的配置
        output_format='html5',
    )
    
    # 2. 渲染内容
    content_html = md.convert(content_markdown)
    
    # 3. 获取 TOC HTML
    # ！！！关键修复：确保缩进正确，toc_html = md.toc or "" 必须与上面对齐 ！！！
    toc_html = md.toc or ""

    return metadata, content_markdown, content_html, toc_html
