# config.py

import os

# --- 站点配置 ---
# 请根据您的实际情况修改
BASE_URL = "https://scaling-parakeet-138.pages.dev/"
# ！！！关键修改：如果您的网站部署在子目录，请在这里填写，否则保持为空""
REPO_SUBPATH = "" 

# 内部链接的根路径
SITE_ROOT = REPO_SUBPATH.rstrip('/')

BLOG_TITLE = "Data Li 的个人网站"
BLOG_DESCRIPTION = "专注于数据科学、极简主义与纯粹的 Web 技术。"
BLOG_AUTHOR = "Data Li"

# 存储 CSS 文件的哈希名
CSS_FILENAME = 'style.css' 

# 定义代码高亮使用的 CSS 类名
CODE_HIGHLIGHT_CLASS = 'highlight'

# --- 目录和文件配置 ---
# ！！！关键：构建输出目录名！！！
BUILD_DIR = '_site' # 默认使用 'build'，如果 Cloudflare 设置的是 '_site' 请修改

POSTS_DIR = 'markdown_posts'
STATIC_DIR = 'assets'

TAGS_DIR_NAME = 'tags' # 标签页面的目录名
SITEMAP_FILE = 'sitemap.xml'
RSS_FILE = 'rss.xml'
MANIFEST_FILE = '.build_manifest.json'

# --- Markdown 配置 ---
# 1. 扩展列表 (使用短名称)
MARKDOWN_EXTENSIONS = [
    'extra',              # 包含 fenced_code (```), tables, footnotes
    'codehilite',         # 代码高亮 (必须安装 Pygments)
    'toc',                # 目录
    'admonition',         # 提示块
    'sane_lists',         # 更好的列表
    'pymdownx.tasklist',  # 任务列表支持 (- [ ])
    'pymdownx.tilde',     # [新增] 删除线支持 (~~text~~)
]

# 2. 扩展具体配置
MARKDOWN_EXTENSION_CONFIGS = {
    'toc': {
        'baselevel': 2,
        'anchorlink': True,
    },
    'codehilite': {
        'linenums': False,             
        'css_class': CODE_HIGHLIGHT_CLASS, 
        'use_pygments': True,          
        'noclasses': False,            # ⭐ 关键修复：改为 False，使用 CSS 类而不是内联样式
        'guess_lang': True,            
    },
    'pymdownx.tasklist': {
        'custom_checkbox': True,      
        'clickable_checkbox': False,  
    }
}
# --- Markdown 配置结束 ---


# --- 列表配置 ---
MAX_POSTS_ON_INDEX = 5
