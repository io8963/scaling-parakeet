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

# NEW: 特殊页面配置
ABOUT_MD_PATH = os.path.join(MD_DIR, 'about.md') # about.md 的源路径
ABOUT_OUTPUT_FILE = 'about.html' # about 页面的输出文件名 (在 BUILD_DIR 根目录)

# 内部目录名
POSTS_DIR = 'posts'
TAGS_DIR = 'tags'
# NEW: 添加 MEDIA_DIR 配置，用于未来可能包含图片等媒体文件的目录
MEDIA_DIR = 'media' # 确保此配置存在，以避免 autobuild.py 中的 AttributeError

# 输出文件/目录路径 (使用 os.path.join 组合)
POSTS_OUTPUT_DIR = os.path.join(BUILD_DIR, POSTS_DIR)
TAGS_OUTPUT_DIR = os.path.join(BUILD_DIR, TAGS_DIR)
INDEX_FILE = 'index.html'
ARCHIVE_FILE = 'archive.html'
TAGS_LIST_FILE = 'tags.html'
SITEMAP_FILE = 'sitemap.xml'
RSS_FILE = 'rss.xml'
