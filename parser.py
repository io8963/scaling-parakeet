# parser.py

import os
import re
import yaml
import markdown
from datetime import datetime, timezone, date
from typing import Dict, Any, Tuple

# MODIFIED: 简化 imports，依赖全部写在 generator.py 或 autobuild.py 中
# from config import * # 避免循环引用，配置在主文件中加载

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
        except yaml.YAMLError as e:
            print(f"Error parsing YAML in {md_file_path}: {e}")
            metadata = {}
    else:
        # 没有 Frontmatter，整个文件是内容
        metadata = {}
        content_markdown = content

    # 转换 Markdown 到 HTML
    md = markdown.Markdown(extensions=[
        'fenced_code',      # 代码块
        'codehilite',       # 代码高亮
        'tables',           # 表格
        'meta',             # 提取元数据 (虽然我们自己处理了)
        'toc'               # 目录
    ])
    content_html = md.convert(content_markdown)
    # 关键修正：获取 TOC HTML
    toc_html = md.toc 


    # 处理日期：确保 date 字段是 datetime 对象
    if 'date' in metadata and isinstance(metadata['date'], date):
        # 如果是 date 对象，转换为 datetime
        metadata['date'] = datetime.combine(metadata['date'], datetime.min.time(), tzinfo=timezone.utc)
    elif 'date' not in metadata:
        # MODIFIED START: 如果没有 date 字段，使用文件的最后修改时间 (mtime) 作为默认值
        try:
            # 获取文件的最后修改时间戳
            mtime_timestamp = os.path.getmtime(md_file_path)
            # 转换为带 UTC 时区的 datetime 对象
            mtime_datetime = datetime.fromtimestamp(mtime_timestamp, tz=timezone.utc)
            metadata['date'] = mtime_datetime
            # print(f"DEBUG: Using mtime {mtime_datetime} for {md_file_path}") # 调试行，可移除
        except Exception as e:
            print(f"Warning: Could not get mtime for {md_file_path}: {e}")
            # 如果获取 mtime 失败，使用当前时间作为保底
            metadata['date'] = datetime.now(timezone.utc)
        # MODIFIED END
        
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
        metadata['tags'] = []
        
    # 返回所有提取到的数据，包括新增的 toc_html
    return metadata, content_markdown, content_html, toc_html
