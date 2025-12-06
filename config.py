# config.py

import os

# --- 站点配置 ---
BASE_URL = "https://aa0.site/"
# ！！！关键修改：请将 "/your-repo-name" 替换为您实际的子目录路径或 GitHub 仓库名
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

# 【新增】首页展示的文章数量
MAX_POSTS_ON_INDEX = 5 

# --- 文件系统配置 ---
POSTS_DIR_NAME = "posts"
PAGES_DIR = "pages"        # <-- 已添加
TAGS_DIR_NAME = "tags"
BUILD_DIR = "_site"
STATIC_DIR = "assets"

# 定义 Sitemap 和 RSS 文件名
SITEMAP_FILE = "sitemap.xml"
RSS_FILE = "rss.xml"


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

# 2. 扩展具体配置 (！！！关键修复：使用短名称作为键！！！)
MARKDOWN_EXTENSION_CONFIGS = {
    'toc': {
        'baselevel': 2,
        'anchorlink': True,
    },
    'codehilite': {
        'linenums': False,             
        'css_class': CODE_HIGHLIGHT_CLASS, # 强制指定类名为 'highlight'
        'use_pygments': True,          # 强制使用 Pygments
        'noclasses': False,            # ⭐ 关键修复：改为 False，使用 CSS 类而不是内联样式
        'guess_lang': True,            # 自动猜测语言
    },
    'pymdownx.tasklist': {
        'custom_checkbox': True,
        'clickable_checkbox': False,
    },
}
