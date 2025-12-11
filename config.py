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

# --- Markdown 配置 ---
# 1. 扩展列表
# 注意：我们替换了 codehilite 为 pymdownx.highlight 和 pymdownx.superfences
# 这能更好地处理代码块嵌套和语言标签识别
MARKDOWN_EXTENSIONS = [
    'extra',              # 包含 fenced_code (```), tables, footnotes
    'toc',                # 目录
    'admonition',         # 提示块
    'sane_lists',         # 更好的列表
    'pymdownx.tasklist',  # 任务列表支持 (- [ ])
    'pymdownx.tilde',     # 删除线支持 (~~text~~)
    'pymdownx.highlight', # [新增] 更强的代码高亮引擎
    'pymdownx.superfences', # [新增] 更好的代码块嵌套支持
]

# 2. 扩展具体配置
MARKDOWN_EXTENSION_CONFIGS = {
    'toc': {
        'baselevel': 2,
        'anchorlink': True,
    },
    'pymdownx.highlight': {
        'use_pygments': True,          # 使用 Pygments 生成高亮类
        'css_class': 'highlight',      # 容器类名
        'guess_lang': True,            # 自动猜测语言
        'anchor_linenums': True,       # 这里的行号配置更灵活
        'pygments_style': 'default',   # 默认样式，实际会被 CSS 覆盖
        'noclasses': False,            # 必须为 False，以便使用 CSS 类
    },
    'pymdownx.superfences': {
        'css_class': 'highlight',      # 确保 fenced code 也有这个类
    },
    'pymdownx.tasklist': {
        'custom_checkbox': True,      # 允许使用 CSS 自定义样式
        'clickable_checkbox': False,  # 静态页面通常设为不可点击
    }
}
# --- Markdown 配置结束 ---


# --- 列表配置 ---
MAX_POSTS_ON_INDEX = 5 

# --- 目录和文件配置 ---
MARKDOWN_DIR = 'markdown'
BUILD_DIR = '_site'
POSTS_DIR_NAME = 'posts' 
TAGS_DIR_NAME = 'tags' 
STATIC_DIR = 'static'
MEDIA_DIR = 'media'

ABOUT_PAGE = 'about.md'

# 特殊文件名称
SITEMAP_FILE = 'sitemap.xml'
RSS_FILE = 'rss.xml'
ARCHIVE_FILE = 'archive.html' 
TAGS_LIST_FILE = 'tags.html'
