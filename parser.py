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
    match = re.match(r'---\\s*\\n(.*?)\\n---\\s*\\n', content, re.DOTALL)

    if match:
        yaml_data = match.group(1)
        content_markdown = content[len(match.group(0)):]
        try:
            metadata = yaml.safe_load(yaml_data) or {}
        except yaml.YAMLError as e:
            print(f"Error parsing YAML frontmatter in {md_file_path}: {e}")
            metadata = {}
    else:
        metadata = {}
        content_markdown = content

    # --- 核心元数据处理和规范化 ---
    
    # 1. 处理 date: 确保 date 是一个带时区的 datetime 对象
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
            
    # NEW: 添加 'date_formatted_full' 字段，供前端页面展示使用
    # 格式化日期为 'YYYY年MM月DD日 HH:MM' (例如: 2023年12月04日 17:22)
    # 使用strftime进行格式化
    if 'date' in metadata and isinstance(metadata['date'], datetime):
        # 注意：使用本地化格式 YYYY年MM月DD日
        metadata['date_formatted_full'] = metadata['date'].strftime('%Y年%m月%d日 %H:%M')
    else:
        # 保底值
        metadata['date_formatted_full'] = "未知日期"
        
    # 2. 处理 tags：确保 tags 字段是一个列表，并转换为 slug
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
        metadata['tags'] = [] # 确保 tag 始终是列表

    # 3. 处理 slug
    if 'slug' not in metadata:
        # 尝试从文件名生成 slug
        file_name = os.path.basename(md_file_path)
        base_name = os.path.splitext(file_name)[0]
        # 假设文件名是日期+标题的组合，例如 2023-12-04-my-post.md
        # 移除日期前缀，使用剩余部分作为 slug
        slug_match = re.match(r'^\d{4}-\d{2}-\d{2}-(.*)$', base_name)
        if slug_match:
            metadata['slug'] = slug_match.group(1).lower()
        else:
             # 如果文件名不是标准格式，使用整个文件名
            metadata['slug'] = base_name.lower()
    
    # 4. 处理 title
    if 'title' not in metadata:
        metadata['title'] = metadata['slug'].replace('-', ' ').title() # 简单的标题化

    # 5. 处理 description/excerpt
    # 如果没有 description 或 excerpt，留空，交给调用方处理 KeyError (已在 generator.py 中修复)
    # metadata['excerpt'] = metadata.get('excerpt', metadata.get('description', ''))
    
    # --- Markdown 渲染 ---
    
# 位于 parser.py 约 120 行附近
# --- Markdown 渲染 ---

# 1. 设置 Markdown 扩展
md = markdown.Markdown(
    extensions=config.MARKDOWN_EXTENSIONS, # 使用配置中的扩展列表
    extension_configs=config.MARKDOWN_EXTENSION_CONFIGS, # 使用配置中的扩展设置
    output_format='html5',
)
# ...
# 2. 渲染内容
content_html = md.convert(content_markdown)
# ...
    
    # 3. 提取目录 (TOC) HTML
    # md.toc 是 toc 扩展生成的内容
    toc_html = md.toc or ""

    return metadata, content_markdown, content_html, toc_html
