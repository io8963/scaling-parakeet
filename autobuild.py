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

# --- Git 时间辅助函数 ---
def get_git_author_time(filepath: str) -> Optional[datetime]:
    """使用 Git 命令获取文件的最新修改时间 (Author Date)，并转换为 UTC+8。"""
    if not os.path.exists('.git'):
        return None # 如果不是 Git 仓库，则返回 None

    try:
        # 获取最新的提交 AuthorDate
        cmd = shlex.split(f'git log -1 --format=%aI -- {filepath}')
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
        date_iso = result.stdout.strip()
        
        if date_iso:
            # 解析 ISO 8601 格式的时间，并将其转换为 UTC+8
            dt_utc = datetime.fromisoformat(date_iso).astimezone(timezone.utc)
            dt_cn = dt_utc.astimezone(TIMEZONE_INFO)
            return dt_cn
    except subprocess.CalledProcessError as e:
        # 文件可能没有被 Git 追踪
        pass
    except ValueError:
        # 日期格式解析失败
        pass
    except Exception as e:
        print(f"Error getting Git time for {filepath}: {e}")
    
    return None

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
        
        if minified_hash != old_hash:
            # 如果哈希变了，或哈希文件名变了，则写入新文件
            with open(css_output_path, 'w', encoding='utf-8') as f:
                f.write(minified_css_content)
            print(f"   -> Generated new CSS file: {new_css_filename}")
        else:
            # 如果哈希没变，则沿用旧文件名
            old_css_filename = old_manifest.get(manifest_key, {}).get('output_filename', 'style.css')
            config.CSS_FILENAME = old_css_filename
            print(f"   -> [SKIP] CSS file unchanged. Using: {config.CSS_FILENAME}")

        # 记录到新清单
        new_manifest[manifest_key] = { 'hash': minified_hash, 'output_filename': config.CSS_FILENAME }

    except Exception as e:
        print(f"Error processing style.css: {e}")
        # 如果出错，继续使用默认值
        config.CSS_FILENAME = 'style.css'
        
    # 2. 处理其他静态文件 (e.g., CNAME, favicons, robots.txt 等)
    static_files = glob.glob('assets/*.*') # 查找 assets 目录下的所有文件
    # 排除 style.css，因为它已被特殊处理
    files_to_copy = [f for f in static_files if os.path.basename(f) != 'style.css'] 
    
    # 复制 CNAME
    cname_path = 'CNAME'
    if os.path.exists(cname_path):
        files_to_copy.append(cname_path)

    for source_path in files_to_copy:
        file_name = os.path.basename(source_path)
        
        # 确定目标路径 (对于 CNAME, 直接到 _site/; 对于 assets/*.* 到 _site/assets/)
        if source_path == 'CNAME':
            output_path = os.path.join(config.BUILD_DIR, file_name)
        else:
            output_path = os.path.join(STATIC_OUTPUT_DIR, file_name)
            
        manifest_key = source_path
        new_file_hash = calculate_file_hash(source_path)
        old_file_hash = old_manifest.get(manifest_key, {}).get('hash')

        if new_file_hash != old_file_hash:
            # 复制文件
            shutil.copy2(source_path, output_path)
            print(f"   -> Copied/Updated: {file_name}")
            new_manifest[manifest_key] = {'hash': new_file_hash}
        else:
            print(f"   -> [SKIP] Static file {file_name} unchanged.")
            new_manifest[manifest_key] = old_manifest[manifest_key]


# --- 核心构建逻辑 ---
def run_build():
    """执行完整的静态站点生成过程。"""
    global_build_time = datetime.now(TIMEZONE_INFO)
    # 格式化构建时间信息 (中文友好)
    global_build_time_cn = global_build_time.strftime("%Y-%m-%d %H:%M:%S")

    print(f"--- 1. 开始构建 (Time: {global_build_time_cn} UTC+8) ---")
    
    # 初始化清单
    old_manifest = load_manifest()
    new_manifest: Dict[str, Any] = {}
    
    theme_changed = False
    # 检查模板文件是否变化（简化：如果任何一个模板文件变化，则认为主题变化）
    template_files = glob.glob(os.path.join(os.path.dirname(__file__), 'templates', '*.html'))
    for t_file in template_files:
        t_hash = calculate_file_hash(t_file)
        t_key = f'template:{os.path.basename(t_file)}'
        if t_hash != old_manifest.get(t_key, {}).get('hash'):
            theme_changed = True
            print(f"   -> Template file changed: {os.path.basename(t_file)}")
        new_manifest[t_key] = {'hash': t_hash}
    if theme_changed:
        print("   -> Theme/Template changed. Forcing all content rebuild.")

    # ------------------------------------------------------------------
    # 步骤 2: 清理旧构建目录 (如果存在)
    # ------------------------------------------------------------------
    if os.path.exists(config.BUILD_DIR):
        print(f"--- 2. 清理 {config.BUILD_DIR} 目录 ---")
        try:
            shutil.rmtree(config.BUILD_DIR)
        except OSError as e:
            print(f"Error: Directory cleanup failed: {e}")
            return
    os.makedirs(config.BUILD_DIR, exist_ok=True)


    # ------------------------------------------------------------------
    # 步骤 3: 复制静态资源 (在这一步会更新 config.CSS_FILENAME)
    # ------------------------------------------------------------------
    copy_static_files(old_manifest, new_manifest)


    # ------------------------------------------------------------------
    # ⭐ 步骤 4: 处理文章 (Posts) - 核心修复部分
    # ------------------------------------------------------------------
    print(f"--- 4. 处理文章 ({config.POSTS_DIR_NAME}) ---")
    os.makedirs(POSTS_OUTPUT_DIR, exist_ok=True)
    all_posts: List[Dict[str, Any]] = []
    tag_map = defaultdict(list)
    
    md_files = glob.glob(os.path.join(config.POSTS_DIR_NAME, '*.md'))
    
    for md_file in md_files:
        file_name = os.path.basename(md_file)
        manifest_key = md_file
        new_file_hash = calculate_file_hash(md_file)
        old_file_hash = old_manifest.get(manifest_key, {}).get('hash')
        
        # 检查文件是否需要重建 (文件哈希变动 或 主题变动)
        if new_file_hash != old_file_hash or theme_changed:
            
            # 1. 解析 Markdown 文件
            metadata, content_markdown, content_html, toc_html = get_metadata_and_content(md_file)
            
            if not metadata:
                print(f" -> [ERROR] Skipping post {md_file} due to missing metadata.")
                continue

            # 2. 收集文章数据
            post: Dict[str, Any] = {
                'md_path': md_file,
                # 修复链接：使用 slug 而不是文件名作为链接
                'link': f"{config.POSTS_DIR_NAME}/{metadata['slug']}.html", 
                'title': metadata.get('title', file_name),
                'date_obj': metadata.get('date_obj'),
                'date_str': metadata.get('date_str', 'Unknown'),
                'tags': metadata.get('tags', []),
                'summary': metadata.get('summary', content_markdown[:200].strip()),
                'content_html': content_html, # 包含完整的 HTML 内容
                'toc_html': toc_html,
                'is_hidden': metadata.get('hidden', False), # 检查是否隐藏
            }

            # 尝试获取 Git Author Time 作为最终发布时间 (如果 date 字段缺失)
            if post['date_obj'] is None:
                 git_time = get_git_author_time(md_file)
                 post['date_obj'] = git_time or global_build_time
                 post['date_str'] = (git_time or global_build_time).strftime('%Y-%m-%d %H:%M:%S')

            # 3. 生成文章 HTML
            if not post['is_hidden']:
                # generator.py 内部会触发 HTML Minify
                generator.generate_post_html(post, global_build_time_cn)
                
            # 4. 收集用于生成索引/归档/标签的数据
            all_posts.append(post)
            for tag in post['tags']:
                tag_map[tag].append(post)
                
            # 5. 更新清单
            new_manifest[manifest_key] = {
                'hash': new_file_hash, 
                'link': generator.make_internal_url(post['link']), # 使用 pretty URL 格式保存
            }
            
        else:
            # 文件未变，沿用旧清单数据
            post = {'is_hidden': False} # 必须有一个 placeholder
            # 必须从旧清单中恢复链接信息，否则在生成 Index/Sitemap 时会丢失链接
            if 'link' in old_manifest.get(manifest_key, {}):
                restored_link = old_manifest[manifest_key]['link']
                # 提取 slug (例如 /posts/hello-world/ -> hello-world)
                slug = restored_link.strip('/').split('/')[-1]
                # 恢复为 posts/slug.html 的原始格式，供后续处理
                post['link'] = f"{config.POSTS_DIR_NAME}/{slug}.html"
            
            all_posts.append(post)
            new_manifest[manifest_key] = old_manifest[manifest_key]
            print(f"   -> [SKIP] Post {file_name} unchanged.")
    
    # 对文章按日期排序 (最新在前)
    # 这里的 all_posts 包含所有文章（包括跳过的），但跳过的文章中 post['date_obj'] 可能为 None
    # 过滤掉没有 date_obj 的（即那些没有被解析且不是新文章的），并重新解析一次元数据
    # 确保排序是基于实际日期的。
    posts_to_sort: List[Dict[str, Any]] = []
    for post in all_posts:
        if 'date_obj' in post and post['date_obj']:
            posts_to_sort.append(post)
        elif 'md_path' in post:
            # 如果是跳过的文章，但需要其日期进行排序，重新解析 metadata 即可
            # 重新解析是安全的，因为它只读取元数据部分
            try:
                metadata, _, _, _ = get_metadata_and_content(post['md_path'], only_metadata=True)
                post['date_obj'] = metadata.get('date_obj')
                post['is_hidden'] = metadata.get('hidden', False)
                if post['date_obj']:
                    posts_to_sort.append(post)
            except Exception as e:
                print(f" -> [WARN] Could not retrieve metadata for sorting/hiding: {post.get('md_path', 'N/A')}. Error: {e}")
                
    
    # 按照日期排序（降序：最新在前）
    # ⚠️ 修复：过滤掉 is_hidden=True 的文章，只对可见文章进行排序和导航链接生成
    visible_posts = [p for p in posts_to_sort if not generator.is_post_hidden(p)]
    visible_posts.sort(key=lambda x: x['date_obj'], reverse=True)
    

    # ------------------------------------------------------------------
    # 步骤 5: 处理独立页面 (Pages)
    # ------------------------------------------------------------------
    print(f"--- 5. 处理独立页面 ({config.PAGES_DIR}) ---")
    os.makedirs(config.BUILD_DIR, exist_ok=True) # 独立页面直接在 _site/ 根目录
    
    page_files = glob.glob(os.path.join(config.PAGES_DIR, '*.md'))
    for page_file in page_files:
        file_name = os.path.basename(page_file)
        base_name = os.path.splitext(file_name)[0]
        manifest_key = page_file
        new_file_hash = calculate_file_hash(page_file)
        old_file_hash = old_manifest.get(manifest_key, {}).get('hash')
        
        # 检查文件是否需要重建 (文件哈希变动 或 主题变动)
        if new_file_hash != old_file_hash or theme_changed:
            metadata, content_markdown, content_html, toc_html = get_metadata_and_content(page_file)
            
            # generator.py 内部会触发 HTML Minify
            generator.generate_page_html(
                content_html=content_html, 
                page_title=metadata.get('title', base_name.title()),
                page_id=base_name,
                # 修复：独立页面应该生成在 /base_name/index.html 或 /base_name.html。这里使用 /base_name.html
                canonical_path_with_html=f'/{base_name}.html',
                build_time_info=global_build_time_cn
            )
            
            new_manifest[manifest_key] = {'hash': new_file_hash}
        else:
            print(f"   -> [SKIP] Page {file_name} unchanged.")
            new_manifest[manifest_key] = old_manifest[manifest_key]

    # ------------------------------------------------------------------
    # ⭐ 步骤 6: 生成主页、归档、标签页和站点地图 - 核心修复部分
    # ------------------------------------------------------------------
    print("--- 6. 生成站点页面 (Index, Archive, Tags, Sitemap, RSS) ---")
    
    # 1. 生成文章之间的导航链接 (Prev/Next)
    generator.add_prev_next_links(visible_posts)

    # 2. 生成主页 (Index)
    generator.generate_index_html(visible_posts, global_build_time_cn)
    
    # 3. 生成归档页 (Archive)
    generator.generate_archive_html(visible_posts, global_build_time_cn)
    
    # 4. 生成标签列表页
    generator.generate_tags_list_html(tag_map, global_build_time_cn)
    
    # 5. 生成每个标签的文章列表页
    for tag, posts_list in tag_map.items():
        # 标签页内的文章也应只显示可见文章
        visible_tag_posts = [p for p in posts_list if not generator.is_post_hidden(p)]
        # 标签页内的文章也按日期排序
        visible_tag_posts.sort(key=lambda x: x['date_obj'], reverse=True)
        generator.generate_tag_page(tag, visible_tag_posts, global_build_time_cn)

    # 6. 生成 Sitemap
    generator.generate_sitemap(visible_posts, page_files)
    
    # 7. 生成 RSS
    generator.generate_rss(visible_posts, global_build_time)


    # ------------------------------------------------------------------
    # 步骤 7: 保存清单
    # ------------------------------------------------------------------
    print("--- 7. 保存构建清单 ---\n")
    # 检查 new_manifest 是否包含任何文章链接，如果 build_manifest.json 依然是空的，说明 post processing 失败
    post_link_count = sum(1 for k in new_manifest.keys() if k.startswith('posts/'))
    print(f"   -> Manifest contains {post_link_count} posts links.")

    save_manifest(new_manifest)
    print(f"--- 构建完成 (耗时: {(datetime.now(TIMEZONE_INFO) - global_build_time).total_seconds():.2f}s) ---")
    
    
# 【移除原文件中冗余的 is_post_hidden 临时定义，统一由 generator.py 提供】

if __name__ == '__main__':
    run_build()
