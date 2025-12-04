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
    'fenced_code',  # ！！！关键修复：必须显式启用此扩展才能识别 ``` 代码块
    'codehilite',   # 启用代码高亮
    'toc', 
    'admonition', 
    'nl2br',        # 可选：将换行符视为 <br>
    'tables',       # 确保表格扩展启用
]

# ！！！关键修复：Markdown 扩展配置 ！！！
MARKDOWN_EXTENSION_CONFIGS = {
    'markdown.extensions.toc': {
        'baselevel': 2, # TOC 从 h2 开始生成
        'anchorlink': True, # 启用锚点链接
        # slugify 函数将在 parser.py 中动态添加
    },
    'markdown.extensions.codehilite': {
        'linenums': False,             # 是否显示行号，建议 False 保持简洁
        'css_class': CODE_HIGHLIGHT_CLASS, # 使用 'highlight' 类名
        'use_pygments': True,          # 使用 Pygments 库进行高亮
        'noclasses': True,             # True=使用内联样式(兼容性好), False=需要额外的 pygments.css
        'guess_lang': True,            # 自动猜测语言
    }
}
# --- Markdown 配置结束 ---


# --- 列表配置 ---
# 首页显示的文章数量
MAX_POSTS_ON_INDEX = 5 

# --- 目录和文件配置 ---
# Markdown 源文件所在的根目录
MARKDOWN_DIR = 'markdown'
# 构建输出目录
BUILD_DIR = '_site'
# 存放文章的子目录名称（在 BUILD_DIR 内）
POSTS_DIR_NAME = 'posts' 
# 存放标签页面的子目录名称（在 BUILD_DIR 内）
TAGS_DIR_NAME = 'tags' 
# 存放静态资源的目录（如 favicon, robots.txt, sitemap.xml 等）
STATIC_DIR = 'static'
# 存放媒体文件（图片、视频等）的目录
MEDIA_DIR = 'media'

ABOUT_PAGE = 'about.md'


# 组合后的输出目录
POSTS_OUTPUT_DIR = os.path.join(BUILD_DIR, POSTS_DIR_NAME)
TAGS_OUTPUT_DIR = os.path.join(BUILD_DIR, TAGS_DIR_NAME)
STATIC_OUTPUT_DIR = os.path.join(BUILD_DIR, STATIC_DIR)

# 特殊文件名称
SITEMAP_FILE = 'sitemap.xml'
RSS_FILE = 'rss.xml'
ARCHIVE_FILE = 'archive.html' 
TAGS_LIST_FILE = 'tags.html' 

# --- 目录配置结束 ---
