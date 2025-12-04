# config.py

import os

# --- 站点配置 ---
BASE_URL = "https://web0863.pages.dev/"
# ！！！关键修改：请将 "/your-repo-name" 替换为您实际的子目录路径或 GitHub 仓库名
REPO_SUBPATH = "" 

# 内部链接的根路径 (确保没有尾部斜杠)
SITE_ROOT = REPO_SUBPATH.rstrip('/')

BLOG_TITLE = "Data Li 的个人网站"
BLOG_DESCRIPTION = "专注于数据科学、极简主义与纯粹的 Web 技术。"
BLOG_AUTHOR = "Data Li"

# --- 列表配置 ---
# 首页显示的文章数量
MAX_POSTS_ON_INDEX = 5 

# --- 目录和文件配置 ---
BUILD_DIR = '_site'         # 构建输出目录
MD_DIR = 'markdown'         # 源文件目录

# 内部目录名
POSTS_DIR = 'posts'
TAGS_DIR = 'tags'

# 输出文件/目录路径 (使用 os.path.join 组合)
POSTS_OUTPUT_DIR = os.path.join(BUILD_DIR, POSTS_DIR)
TAGS_OUTPUT_DIR = os.path.join(BUILD_DIR, TAGS_DIR)

# 静态文件目录
STATIC_DIR = 'static'
# 静态文件构建输出路径
STATIC_OUTPUT_DIR = os.path.join(BUILD_DIR, STATIC_DIR)
# 媒体文件目录
MEDIA_DIR = 'media'
MEDIA_OUTPUT_DIR = os.path.join(BUILD_DIR, MEDIA_DIR)

# 输出文件名
INDEX_FILE = 'index.html'
ARCHIVE_FILE = 'archive.html'
TAGS_FILE = 'tags.html'
ABOUT_FILE = 'about.html'
SITEMAP_FILE = 'sitemap.xml'
RSS_FILE = 'rss.xml'
# 新增：关于页面的 Markdown 文件名
ABOUT_MD_FILE = 'about.md'
