# parser.py

import os
import re
import yaml
import markdown
from datetime import datetime, timezone, date
from typing import Dict, Any, Tuple
import config # 修正 1: 导入 config 文件以使用统一的 Markdown 扩展配置

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
        # 修正：返回四个空值
        return {}, "", "", ""

    # 使用正则表达式分隔 Frontmatter (--- ... ---) 和内容
    # 匹配 YAML Front Matter 块
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
        # 整个文件都是内容
        content_markdown = content
        metadata = {}
        
    # 优化建议 5: 使用 config 中定义的 Markdown 扩展列表
    md = markdown.Markdown(
        extensions=config.MARKDOWN_EXTENSIONS 
    )
    
    # 转换 Markdown 到 HTML
    content_html = md.convert(content_markdown)
    toc_html = md.toc # TOC 扩展自动生成的目录 HTML

    # 处理 date 字段
    if 'date' in metadata and isinstance(metadata['date'], date) and not isinstance(metadata['date'], datetime):
        # 将 date 对象转换为 UTC 时区的 datetime
        metadata['date'] = datetime.combine(metadata['date'], datetime.min.time(), tzinfo=timezone.utc)
    elif 'date' not in metadata:
        # 如果没有 date 字段，使用文件的最后修改时间 (mtime) 作为默认值
        try:
            # 获取文件的最后修改时间戳
            mtime_timestamp = os.path.getmtime(md_file_path)
            # 转换为带 UTC 时区的 datetime 对象
            mtime_datetime = datetime.fromtimestamp(mtime_timestamp, tz=timezone.utc)
            metadata['date'] = mtime_datetime
        except Exception as e:
            print(f"Warning: Could not get mtime for {md_file_path}: {e}")
            # 如果获取 mtime 失败，使用当前时间作为保底
            metadata['date'] = datetime.now(timezone.utc)
        
    # 处理 tags：确保 tags 字段是一个列表，并转换为 slug
    if 'tags' in metadata:
        if isinstance(metadata['tags'], str):
            # 如果是逗号分隔的字符串，分割成列表
            tags_list = [t.strip() for t in metadata['tags'].split(',') if t.strip()]
        elif isinstance(metadata['tags'], list):
            tags_list = [t.strip() for t in metadata['tags'] if isinstance(t, str) and t.strip()]
        else:
            tags_list = []
            
        metadata['tags'] = [
            {'name': t, 'slug': tag_to_slug(t)}
            for t in tags_list
        ]
    else: 
        # 修正 2: 关键修复，如果 metadata 中没有 tags 键，则初始化为空列表，防止 KeyError
        metadata['tags'] = []
        
    return metadata, content_markdown, content_html, toc_html
