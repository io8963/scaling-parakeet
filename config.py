# config.py

import os

# --- 站点配置 ---
BASE_URL = "https://scaling-parakeet-138.pages.dev/"
# ！！！关键修改：请将 "/your-repo-name" 替换为您实际的子目录路径或 GitHub 仓库名
REPO_SUBPATH = "" 

# 内部链接的根路径 (确保没有尾部斜杠)
SITE_ROOT = REPO_SUBPATH.rstrip('/')

BLOG_TITLE = "Data Li 的个人网站"
BLOG_DESCRIPTION = "专注于数据科学、极简主义与纯粹的 Web 技术。"
BLOG_AUTHOR = "Data Li"

# NEW: 存储 CSS 文件的哈希名，在 autobuild.py 中设置
CSS_FILENAME = 'style.css' 

# NEW: 存储代码高亮 CSS 类的名称（Pygments 默认类名）
CODE_HIGHLIGHT_CLASS = 'highlight'

# --- Markdown 配置 ---
# 默认的 Markdown 扩展列表
MARKDOWN_EXTENSIONS = [
    'extra', 
    'fenced_code', 
    'codehilite', 
    'toc', 
    'admonition', 
]
# ！！！关键修复：Markdown 扩展配置 ！！！
MARKDOWN_EXTENSION_CONFIGS = {
    'markdown.extensions.toc': {
        'baselevel': 2, # TOC 从 h2 开始生成
        'anchorlink': True, # 启用锚点链接
        # slugify 函数将在 parser.py 中动态添加，因为它依赖于 parser.py 内部函数
    },
    'markdown.extensions.codehilite': {
        # 允许代码块复制功能
        'linenums': False,
        'css_class': CODE_HIGHLIGHT_CLASS, # 使用 config 中的类名
        'use_pygments': True, # 确保使用 Pygments
        'noclasses': True, # 强制内联样式，如果需要外置样式，设置为 False
    }
}
# --- Markdown 配置结束 ---


# --- 列表配置 ---
# 首页显示的文章数量
MAX_POSTS_ON_INDEX = 5 

# --- 目录和文件配置 ---
BUILD_DIR = '_site'         # 构建输出目录
MD_DIR = 'markdown'         # 源文件目录

# 内部目录名
POSTS_DIR = 'posts'
TAGS_DIR = 'tags'
MEDIA_DIR = 'media' 
STATIC_DIR = 'static' # 静态文件源目录

# 输出文件/目录路径 (使用 os.path.join 组合)
POSTS_OUTPUT_DIR = os.path.join(BUILD_DIR, POSTS_DIR)
TAGS_OUTPUT_DIR = os.path.join(BUILD_DIR, TAGS_DIR)
STATIC_OUTPUT_DIR = os.path.join(BUILD_DIR, STATIC_DIR)

# 特殊文件
INDEX_FILE = 'index.html'
ARCHIVE_FILE = 'archive.html'
TAGS_LIST_FILE = 'tags.html'
ABOUT_OUTPUT_FILE = 'about.html'
SITEMAP_FILE = 'sitemap.xml'
RSS_FILE = 'rss.xml'
