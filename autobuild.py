# autobuild.py - 启用增量构建并修复独立时间

import os
import shutil
import glob
import hashlib
import json
from typing import List, Dict, Any, Set, Optional 
from collections import defaultdict
from datetime import datetime, timezone, timedelta 
import subprocess 
import shlex      

import config
from parser import get_metadata_and_content
import generator
import rcssmin # <-- 导入：用于 CSS Minify

# =========================================================================
# 【关键修复】将组合后的输出目录变量移到此处，以解决 config 模块属性缺失的问题
# =========================================================================
# 这些变量现在是 autobuild.py 模块的全局变量，确保可用
POSTS_OUTPUT_DIR = os.path.join(config.BUILD_DIR, config.POSTS_DIR_NAME)
TAGS_OUTPUT_DIR = os.path.join(config.BUILD_DIR, config.TAGS_DIR_NAME)
STATIC_OUTPUT_DIR = os.path.join(config.BUILD_DIR, config.STATIC_DIR)
# =========================================================================


# [恢复] 定义清单文件路径
MANIFEST_FILE = os.path.join(os.path.dirname(__file__), '.build_manifest.json')

# 定义 UTC+8 时区信息
TIMEZONE_OFFSET = timedelta(hours=8)
TIMEZONE_INFO = timezone(TIMEZONE_OFFSET)

# --- Manifest 辅助函数 (增量构建所需) ---
def load_manifest() -> Dict[str, Any]:
    """加载上一次的构建清单文件。"""
    try:
        with open(MANIFEST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_manifest(manifest_data: Dict[str, Any]):
    """保存当前的构建清单文件。"""
    try:
        with open(MANIFEST_FILE, 'w', encoding='utf-8') as f:
            json.dump(manifest_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving manifest: {e}")

# --- 文件哈希辅助函数 ---
def calculate_file_hash(filepath: str) -> str:
    """计算文件的 SHA256 哈希值。"""
    try:
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            # 分块读取，适用于大文件
            for chunk in iter(lambda: f.read(4096), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        return ""
    except Exception as e:
        print(f"Error hashing {filepath}: {e}")
        return ""

# --- 关键：静态文件复制和 CSS Minify ---
def copy_static_files(old_manifest: Dict[str, Any], new_manifest: Dict[str, Any]):
    """
    复制静态资源，包括 CSS 文件。
    如果 style.css 内容有变化，则重新生成带有哈希名的 CSS 文件。
    """
    print("--- 3. 复制静态资源 ---")
    
    # 确保输出目录存在
    os.makedirs(STATIC_OUTPUT_DIR, exist_ok=True)

    # 1. 处理 style.css
    css_source_path = os.path.join('assets', 'style.css')
    css_output_base = 'style' # 例如：style.css
    
    try:
        with open(css_source_path, 'r', encoding='utf-8') as f:
            css_content = f.read()
            
        # ⭐⭐⭐ CSS Minification 核心逻辑 ⭐⭐⭐
        minified_css_content = rcssmin.cssmin(css_content) 
        print("   -> CSS Minify: 原始大小 {} bytes -> 最小化大小 {} bytes".format(
            len(css_content.encode('utf-8')), 
            len(minified_css_content.encode('utf-8'))
        ))
        
        # 计算最小化后的内容的哈希
        minified_hash = hashlib.sha256(minified_css_content.encode('utf-8')).hexdigest()[:8]
        new_css_filename = f"{css_output_base}.{minified_hash}.css"
        css_output_path = os.path.join(STATIC_OUTPUT_DIR, new_css_filename)
        
        # 将新文件名存入 config 供 generator.py 使用
        config.CSS_FILENAME = new_css_filename
        
        # 检查是否需要重新写入文件
        manifest_key = 'assets/style.css'
        old_hash = old_manifest.get(manifest_key, {}).get('hash')
        new_hash = calculate_file_hash(css_source_path) # 仍然基于源文件判断是否要写入
        
        # 只有在文件变化或目标哈希文件不存在时，才写入
        if old_hash != new_hash or not os.path.exists(css_output_path):
            print(f"   -> Writing new CSS file: {new_css_filename}")
            # 写入最小化后的内容
            with open(css_output_path, 'w', encoding='utf-8') as f:
                f.write(minified_css_content)
        else:
            print(f"   -> Skipping {css_output_base}.css (unchanged)")
            # 如果源文件未变，尝试从旧清单中获取正确的哈希名
            old_css_filename = old_manifest.get(manifest_key, {}).get('output_filename', config.CSS_FILENAME)
            if old_hash == new_hash and os.path.exists(os.path.join(STATIC_OUTPUT_DIR, old_css_filename)):
                # 如果源文件未变，且旧的哈希文件存在，我们继续使用旧的哈希名
                config.CSS_FILENAME = old_css_filename
                new_css_filename = old_css_filename # 覆盖，防止后面写入 manifest 时出错
            else:
                 # 确保使用当前计算出的新哈希名
                 config.CSS_FILENAME = new_css_filename
            
        # 记录到新清单
        new_manifest[manifest_key] = {
            'hash': new_hash,
            'output_filename': config.CSS_FILENAME 
        }

    except Exception as e:
        print(f"Error processing style.css: {e}")
        # 如果出错，继续使用默认值
        config.CSS_FILENAME = 'style.css'
        
    # 2. 处理其他静态文件 (e.g., CNAME, favicons, robots.txt 等)
    static_files = glob.glob('assets/*.*')
    
    # 排除 style.css，因为它已被特殊处理
    files_to_copy = [f for f in static_files if os.path.basename(f) != 'style.css']
    
    # 复制 CNAME
    cname_path = 'CNAME'
    if os.path.exists(cname_path):
        files_to_copy.append(cname_path)
    
    # 复制其他文件
    for src_path in files_to_copy:
        file_name = os.path.basename(src_path)
        dest_path = os.path.join(STATIC_OUTPUT_DIR, file_name)
        
        manifest_key = src_path
        old_hash = old_manifest.get(manifest_key, {}).get('hash')
        new_hash = calculate_file_hash(src_path)
        
        # 如果哈希值变化或目标文件不存在，则复制
        if old_hash != new_hash or not os.path.exists(dest_path):
            print(f"   -> Copying {src_path}")
            shutil.copy(src_path, dest_path)
        else:
            print(f"   -> Skipping {file_name} (unchanged)")
        
        new_manifest[manifest_key] = {
            'hash': new_hash
        }


def clean_build_directory():
    """清理构建目录"""
    if os.path.exists(config.BUILD_DIR):
        print(f"Cleaning build directory: {config.BUILD_DIR}")
        try:
            # 清除 build 目录内容
            shutil.rmtree(config.BUILD_DIR)
        except OSError as e:
            print(f"Error removing directory {config.BUILD_DIR}: {e}")
            
    # 确保 BUILD_DIR 及其子目录存在
    os.makedirs(config.BUILD_DIR, exist_ok=True)
    os.makedirs(POSTS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(TAGS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(STATIC_OUTPUT_DIR, exist_ok=True)


# --- 核心构建逻辑 ---
def build_site():
    """主构建函数"""
    print(f"--- 1. 初始化构建 (Target: {config.BUILD_DIR}) ---")
    clean_build_directory()
    old_manifest = load_manifest()
    new_manifest = {}
    
    # 计算主题/模板文件的哈希值
    theme_files = glob.glob('templates/*') + glob.glob('*.py')
    theme_hash = calculate_file_hash(os.path.join(os.path.dirname(__file__), 'autobuild.py')) # 至少包含 autobuild.py
    for f in theme_files:
        theme_hash += calculate_file_hash(f)
    
    theme_changed = theme_hash != old_manifest.get('theme_hash')
    if theme_changed:
        print("   -> [ALERT] Theme/Template files changed. Forced full rebuild.")
    
    new_manifest['theme_hash'] = theme_hash
    
    # 全局构建时间 (中国时区)
    global_build_time = datetime.now(TIMEZONE_INFO)
    global_build_time_cn = global_build_time.strftime('%Y-%m-%d %H:%M:%S') + ' CST'
    print(f"   -> Build Time: {global_build_time_cn}")
    
    # ------------------------------------------------------------------
    # 步骤 1: 静态文件处理 (CSS Minify)
    # ------------------------------------------------------------------
    # 注意: 这一步必须在解析文章之前完成，以便 config.CSS_FILENAME 更新
    copy_static_files(old_manifest, new_manifest)

    print("--- 2. 解析 Markdown 文章 ---")
    md_files = glob.glob(os.path.join(config.POSTS_DIR_NAME, '*.md'))
    
    all_posts: List[Dict[str, Any]] = []
    posts_to_build_all: List[Dict[str, Any]] = [] # 需要完全重新生成页面的文章
    posts_data_changed = False # 标记是否有任何文章数据发生变化
    
    for md_file in md_files:
        manifest_key = md_file
        old_file_data = old_manifest.get(manifest_key, {})
        
        # 检查文件是否被修改 (哈希值是否变化)
        new_file_hash = calculate_file_hash(md_file)
        file_changed = new_file_hash != old_file_data.get('hash')
        
        # 只有在文件变化或主题变化时才重新解析
        if file_changed or theme_changed:
            print(f"   -> [PARSE] {md_file}")
            # 调用 parser.py 解析文件，获取 metadata, content_html, toc_html
            metadata, content_markdown, content_html, toc_html = get_metadata_and_content(md_file)
            
            # 记录新的元数据和内容哈希（用于增量构建）
            new_file_data = {
                'hash': new_file_hash,
                'metadata': metadata,
                'content_html': content_html,
                'toc_html': toc_html,
                # 'footer_time_info' 将在后面计算
            }
            posts_data_changed = True
        else:
            # 文件未变化，从旧清单加载数据
            # ⚠️ 必须确保旧清单中的数据结构是完整的
            print(f"   -> [SKIP PARSE] {md_file} (unchanged)")
            metadata = old_file_data.get('metadata', {})
            content_html = old_file_data.get('content_html', '')
            toc_html = old_file_data.get('toc_html', '')
        
        if not metadata:
            print(f"   -> [ERROR] Skipping post {md_file} due to missing metadata.")
            continue
            
        post: Dict[str, Any] = {
            'md_path': md_file,
            'link': f"{config.POSTS_DIR_NAME}/{metadata['slug']}.html", # 始终生成 .html 路径，由 generator 转换为 pretty URL
            'metadata_changed': file_changed, # 标记元数据是否需要重新处理
            'content_html': content_html, 
            'toc_html': toc_html,
        }
        post.update(metadata)
        
        # 获取 Git 提交时间
        if not file_changed and old_file_data.get('footer_time_info'):
            # 如果文件未变且有旧时间信息，则直接使用
            post['footer_time_info'] = old_file_data['footer_time_info']
            new_file_data['footer_time_info'] = post['footer_time_info']
        else:
            # 否则重新计算
            try:
                # 获取最新的提交作者时间 (UTC)
                git_time_str = subprocess.check_output(
                    shlex.split(f'git log -1 --pretty=format:"%aI" -- "{md_file}"')
                ).decode('utf-8').strip()
                
                if git_time_str:
                    # 将 Git 时间转换为 UTC+8
                    git_time_utc = datetime.fromisoformat(git_time_str)
                    local_time = git_time_utc.astimezone(TIMEZONE_INFO)
                    
                    if local_time.date() != post['date']:
                        # 如果 Git 时间和 Frontmatter 日期不一致，则显示两者
                        time_info = f"最后更新: {local_time.strftime('%Y-%m-%d %H:%M:%S')} CST (发布日期: {post['date_formatted']})"
                    else:
                        time_info = f"最后更新: {local_time.strftime('%Y-%m-%d %H:%M:%S')} CST"
                else:
                    # 如果 Git 历史为空，则使用全局构建时间
                    time_info = f"构建于 {global_build_time_cn}"

            except Exception as e:
                # 如果 Git 失败，则使用全局构建时间
                print(f"   -> Git time error for {md_file}: {e}. Using build time.")
                time_info = f"构建于 {global_build_time_cn}"
                
            post['footer_time_info'] = time_info
            # 仅在实际解析时才将 metadata 和 content_html 等保存到清单
            if file_changed or theme_changed:
                 new_manifest[manifest_key] = new_file_data # 写入清单
            else:
                 # 未变化的文件，使用旧的清单数据并更新 footer_time_info (如果需要)
                 new_manifest[manifest_key] = old_file_data
                 new_manifest[manifest_key]['footer_time_info'] = time_info
        
        all_posts.append(post)
        
        # 确定需要重新构建页面的文章列表
        if file_changed or theme_changed:
            posts_to_build_all.append(post)
        else:
            # 即使文件未变，如果上一次的清单里没有 'metadata' 字段 (如旧格式)，也强制重建
            if not old_file_data.get('metadata'):
                posts_to_build_all.append(post)
    
    # 排序文章
    final_parsed_posts = sorted(all_posts, key=lambda p: p['date'], reverse=True)
    
    # 填充导航链接和标签映射
    tag_map = defaultdict(list)
    nav_posts = [p for p in final_parsed_posts if not is_post_hidden(p)] # 仅对公开文章建立导航
    
    for i, post in enumerate(nav_posts):
        # 导航链接
        post['prev_post_nav'] = nav_posts[i-1] if i > 0 else None
        post['next_post_nav'] = nav_posts[i+1] if i < len(nav_posts) - 1 else None
        
        # 标签映射
        for tag in post.get('tags', []):
            tag_map[tag['name']].append(post)
            
    # ------------------------------------------------------------------
    # 步骤 3: 页面生成 (HTML Minify 在 generator.py 中处理)
    # ------------------------------------------------------------------
    print("--- 4. 生成 HTML 页面 ---")
    
    # 1. 生成文章页 (应用增量逻辑)
    if not posts_to_build_all and not theme_changed:
        print("   -> [SKIP] No post data or theme changed. Skipping post regeneration.")
    else:
        print(f"   -> [REBUILD] Generating {len(posts_to_build_all)} post pages.")
        for post in posts_to_build_all:
            # generator.py 内部会触发 HTML Minify
            generator.generate_post_page(post) 
    
    # 2. 生成列表页 (应用增量逻辑)
    if not old_manifest or posts_data_changed or theme_changed: # <-- 关键修改
        print("   -> [REBUILDING] Index, Archive, Tags, RSS (Post data or Theme changed)")
        
        # 这些函数内部也会使用 HTML Minify
        generator.generate_index_html(final_parsed_posts, global_build_time_cn) 
        generator.generate_archive_html(final_parsed_posts, global_build_time_cn) 
        generator.generate_tags_list_html(tag_map, global_build_time_cn) 

        for tag, posts in tag_map.items():
            sorted_tag = sorted(posts, key=lambda p: p['date'], reverse=True)
            # generator.py 内部会触发 HTML Minify
            generator.generate_tag_page(tag, sorted_tag, global_build_time_cn) 

        generator.generate_robots_txt()
        
        # Sitemap & RSS 不进行 HTML Minify (它们是 XML 格式)
        with open(os.path.join(config.BUILD_DIR, config.SITEMAP_FILE), 'w', encoding='utf-8') as f:
            f.write(generator.generate_sitemap(final_parsed_posts))
        with open(os.path.join(config.BUILD_DIR, config.RSS_FILE), 'w', encoding='utf-8') as f:
            f.write(generator.generate_rss(final_parsed_posts))
            
    else:
        print("   -> [SKIP] List pages unchanged.")
        
    # 3. 复制通用页面 (如果存在)
    if os.path.exists(config.PAGES_DIR):
        print("--- 5. 生成通用页面 ---")
        page_files = glob.glob(os.path.join(config.PAGES_DIR, '*.md'))
        for page_file in page_files:
            file_name = os.path.basename(page_file)
            base_name = os.path.splitext(file_name)[0] # 例如 about.md -> about
            
            # 只有在文件变化或主题变化时才重新生成
            manifest_key = page_file
            old_file_hash = old_manifest.get(manifest_key, {}).get('hash')
            new_file_hash = calculate_file_hash(page_file)
            
            if new_file_hash != old_file_hash or theme_changed:
                metadata, content_markdown, content_html, toc_html = get_metadata_and_content(page_file)
                
                # generator.py 内部会触发 HTML Minify
                generator.generate_page_html(
                    content_html=content_html, 
                    page_title=metadata.get('title', base_name.title()),
                    page_id=base_name,
                    canonical_path_with_html=f'/{base_name}.html',
                    build_time_info=global_build_time_cn
                )
                
                new_manifest[manifest_key] = {'hash': new_file_hash}
            else:
                print(f"   -> [SKIP] Page {file_name} unchanged.")
                new_manifest[manifest_key] = old_manifest[manifest_key]
                
    # ------------------------------------------------------------------
    # 步骤 4: 保存清单
    # ------------------------------------------------------------------
    print("--- 6. 保存构建清单 ---")
    save_manifest(new_manifest)
    print(f"--- 构建完成 (耗时: {(datetime.now(TIMEZONE_INFO) - global_build_time).total_seconds():.2f}s) ---")
    
    
def is_post_hidden(post: Dict[str, Any]) -> bool:
    """检查文章是否应被隐藏。"""
    # 临时定义，以确保 autobuild.py 内部的逻辑可以运行。
    # 真正的 is_post_hidden 应该在 generator 或一个 util 文件中。
    # 假设 post 是一个 Dict[str, Any]
    return post.get('status', 'published').lower() == 'draft' or post.get('hidden') is True


if __name__ == '__main__':
    build_site()
