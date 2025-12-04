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

# --- 列表配置 ---
# 首页显示的文章数量
MAX_POSTS_ON_INDEX = 5 

# --- 目录和文件配置 ---
BUILD_DIR = '_site'         # 构建输出目录
MD_DIR = 'markdown'         # 源文件目录

# 内部目录名
POSTS_DIR = 'posts'
TAGS_DIR = 'tags'
# NEW: 添加 MEDIA_DIR 配置，用于未来可能包含图片等媒体文件的目录
MEDIA_DIR = 'media' # 确保此配置存在，以避免 autobuild.py 中的 AttributeError

# 输出文件/目录路径 (使用 os.path.join 组合)
POSTS_OUTPUT_DIR = os.path.join(BUILD_DIR, POSTS_DIR)
TAGS_OUTPUT_DIR = os.path.join(BUILD_DIR, TAGS_DIR)

# 静态文件目录
STATIC_DIR = 'static'
# 静态文件构建输出路径
STATIC_OUTPUT_DIR = os.path.join(BUILD_DIR, STATIC_DIR)

# 特殊文件
ROBOTS_FILE = 'robots.txt'
SITEMAP_FILE = 'sitemap.xml'
RSS_FILE = 'rss.xml'

# --- Markdown 扩展配置 ---

# 使用字典配置来确保 TOC (目录) 和 Pygments (代码高亮) 正常工作
MARKDOWN_EXTENSION_CONFIGS = {
    # 配置 Pygments
    'codehilite': {
        'css_class': CODE_HIGHLIGHT_CLASS,
        'linenums': False, # 不显示行号
        'guess_lang': True,
        'use_pygments': True,
    },
    # 配置 TOC (目录)
    'toc': {
        'baselevel': 2,       # 从 H2 (##) 开始生成目录
        'permalink': True,    # 为标题生成永久链接锚点
    },
}
