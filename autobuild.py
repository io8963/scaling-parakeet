# autobuild.py - 启用增量构建并修复独立时间

import os
import shutil
import glob
import hashlib
import json
# ！！！关键修复：添加 Optional 导入！！！
from typing import List, Dict, Any, Set, Optional
from collections import defaultdict
from datetime import datetime, timezone, timedelta 
import subprocess 
import shlex      

import config
from parser import get_metadata_and_content
import generator

# [新增] 强制清理函数
def clean_build_directory():
    """彻底删除并重建构建目录，以确保没有旧的 .html 文件残留。"""
    build_dir = config.BUILD_DIR # 使用 config.py 中的 BUILD_DIR
    print(f"[BUILD] Cleaning old build directory: {build_dir}")
    if os.path.exists(build_dir):
        try:
            # 强制删除整个目录及其内容
            shutil.rmtree(build_dir)
            print(f"[BUILD] Successfully removed {build_dir}.")
        except Exception as e:
            print(f"[ERROR] Failed to remove {build_dir}: {e}")
    
    # 重新创建目录
    try:
        os.makedirs(build_dir, exist_ok=True)
        print(f"[BUILD] Recreated {build_dir} directory.")
    except Exception as e:
        print(f"[ERROR] Failed to create {build_dir}: {e}")

# [恢复] 定义清单文件路径
MANIFEST_FILE = os.path.join(os.path.dirname(__file__), config.MANIFEST_FILE)

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

def save_manifest(manifest: Dict[str, Any]):
    """保存当前的构建清单文件。"""
    try:
        with open(MANIFEST_FILE, 'w', encoding='utf-8') as f:
            # 使用 config.MANIFEST_FILE 而不是硬编码的文件名
            json.dump(manifest, f, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f"警告：无法写入构建清单文件 {MANIFEST_FILE}: {e}")

def get_full_content_hash(filepath: str) -> str:
    """计算文件的完整 SHA256 哈希值。用于 Manifest。"""
    h = hashlib.sha256()
    # 使用 64KB 块读取文件
    with open(filepath, 'rb') as file:
        while True:
            chunk = file.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def get_git_creation_time(filepath: str) -> Optional[datetime]:
    """尝试使用 Git 历史记录获取文件的初始提交时间。"""
    try:
        # 使用 `git log --format="%at" --diff-filter=A -- [path]` 获取文件首次添加时的 Unix 时间戳
        # `--diff-filter=A` 只查看添加的文件
        command = f'git log --format="%at" --diff-filter=A -- "{filepath}"'
        result = subprocess.run(shlex.split(command), capture_output=True, text=True, check=True, cwd=os.path.dirname(os.path.abspath(__file__)))
        
        # Git log 可能会返回多个时间戳，取最后一个（最早的提交，即创建）
        timestamps = result.stdout.strip().split('\n')
        if timestamps and timestamps[-1].isdigit():
            # 将 Unix 时间戳转换为 datetime 对象，并设为 UTC+8
            timestamp = int(timestamps[-1])
            return datetime.fromtimestamp(timestamp, tz=TIMEZONE_INFO)
        return None
    except subprocess.CalledProcessError as e:
        # 文件可能尚未被 Git 追踪
        # print(f"警告：无法获取 {filepath} 的 Git 创建时间: {e.stderr.strip()}")
        return None
    except Exception:
        return None


# --- 核心构建逻辑 ---

def main():
    # -------------------------------------------------------------------------
    # [1/5] 清理构建目录 (必须在执行其他操作前调用)
    # -------------------------------------------------------------------------
    clean_build_directory()
    # -------------------------------------------------------------------------

    # 1. 记录构建开始时间
    start_time = datetime.now(TIMEZONE_INFO)
    global_build_time_cn = f"最后构建于 {start_time.strftime('%Y年%m月%d日 %H:%M:%S')} (UTC+8)"
    print(f"[1/5] Build started: {global_build_time_cn}")

    # 2. 加载旧清单
    old_manifest = load_manifest()
    new_manifest = {'files': {}, 'posts': {}}
    
    # 3. 解析 Markdown 文件，应用增量逻辑
    print("\n[2/5] Parsing Markdown files...")
    
    # 遍历所有 Markdown 文件
    markdown_files = glob.glob(os.path.join(config.POSTS_DIR, '**', '*.md'), recursive=True)
    all_posts = []
    
    # 标记哪些文章需要重新生成 HTML
    posts_to_build: List[Dict[str, Any]] = []
    # 标记文章数据（内容或元数据）是否发生变化，这会触发列表页重建
    posts_data_changed = False 
    
    for filepath in markdown_files:
        relative_path = os.path.relpath(filepath, config.POSTS_DIR)
        post_key = relative_path.replace(os.path.sep, '/')
        
        # 检查哈希值是否改变
        current_hash = get_full_content_hash(filepath)
        new_manifest['posts'][post_key] = {'hash': current_hash}

        # 尝试使用旧的解析结果
        old_post_data = old_manifest.get('posts', {}).get(post_key)
        
        if old_post_data and old_post_data.get('hash') == current_hash:
            # 只有哈希不变，且旧数据存在时，才使用旧数据
            try:
                # 尝试从 manifest 恢复旧的解析数据 (link, title, date等)
                restored_post = {k: v for k, v in old_post_data.items() if k != 'hash'}
                
                # 重新将日期字符串转换回 datetime 对象
                if 'date_str' in restored_post:
                    restored_post['date'] = datetime.strptime(restored_post['date_str'], '%Y-%m-%d').date()
                
                # 标记为不需要重新构建 HTML
                restored_post['should_build'] = False 
                all_posts.append(restored_post)
                
                # 仅将 hash 写入 new_manifest，其它数据在后面统一写入
                # new_manifest['posts'][post_key]['data'] = restored_post # 留待后面统一处理

            except Exception as e:
                # 恢复失败，需要重新解析
                print(f"  [ERROR] Failed to restore data for {post_key}: {e}. Re-parsing.")
                parsed_post = get_metadata_and_content(filepath, post_key)
                parsed_post['should_build'] = True
                posts_data_changed = True
                all_posts.append(parsed_post)

        else:
            # 哈希改变或无旧数据，需要重新解析
            print(f"  [PARSING] {relative_path}")
            parsed_post = get_metadata_and_content(filepath, post_key)
            parsed_post['should_build'] = True
            posts_data_changed = True
            all_posts.append(parsed_post)


    # 4. 排序、构建文章导航和标签图
    print("\n[3/5] Organizing posts and building map...")
    
    # 移除草稿和隐藏文章
    visible_posts = [p for p in all_posts if not (p.get('status', 'published').lower() == 'draft' or p.get('hidden') is True)]

    # 按日期排序 (最新在前)
    final_parsed_posts = sorted(visible_posts, key=lambda p: p['date'], reverse=True)
    
    tag_map = defaultdict(list)
    
    for i, post in enumerate(final_parsed_posts):
        # 构建上一篇/下一篇导航
        prev_post = final_parsed_posts[i-1] if i > 0 else None
        next_post = final_parsed_posts[i+1] if i < len(final_parsed_posts) - 1 else None
        
        post['prev_post_nav'] = {'title': prev_post['title'], 'link': prev_post['link']} if prev_post else None
        post['next_post_nav'] = {'title': next_post['title'], 'link': next_post['link']} if next_post else None
        
        # 构建标签图
        for tag in post.get('tags', []):
            tag_map[tag['name']].append(post)

        # 检查是否需要重新构建 HTML
        # 如果 post 自身需要构建，或者上一篇/下一篇导航链接变了，都需要重新构建
        if post['should_build'] or \
           (prev_post and prev_post['link'] != old_manifest.get('posts', {}).get(prev_post['link_key'], {}).get('link')) or \
           (next_post and next_post['link'] != old_manifest.get('posts', {}).get(next_post['link_key'], {}).get('link')):
            posts_to_build.append(post)
            new_manifest['posts'][post['link_key']]['should_build'] = True
        else:
            new_manifest['posts'][post['link_key']]['should_build'] = False


    # 5. 生成 HTML (应用增量逻辑)
    # ------------------------------------------------------------------------
    print("\n[4/5] Generating HTML...")
    
    # 1. 生成普通文章详情页 (只生成变动的)
    for post in posts_to_build:
        generator.generate_post_page(post) 

    # 2. 生成列表页 (应用增量逻辑)
    if not old_manifest or posts_data_changed:
        print("   -> [REBUILDING] Index, Archive, Tags, RSS (Post data changed)")
        
        generator.generate_index_html(final_parsed_posts, global_build_time_cn) 
        generator.generate_archive_html(final_parsed_posts, global_build_time_cn) 
        generator.generate_tags_list_html(tag_map, global_build_time_cn) 

        for tag, posts in tag_map.items():
            sorted_tag = sorted(posts, key=lambda p: p['date'], reverse=True)
            generator.generate_tag_page(tag, sorted_tag, global_build_time_cn) 

        generator.generate_robots_txt()
        
        # 3. 生成 about.html (如果存在 about.md)
        about_md_path = os.path.join(config.POSTS_DIR, 'about.md')
        if os.path.exists(about_md_path):
            about_data = get_metadata_and_content(about_md_path, 'about.html')
            generator.generate_page_html(
                content_html=about_data['content_html'], 
                page_title=about_data.get('title', '关于'), 
                page_id='about', 
                canonical_path_with_html='about.html', # 传递带 .html 的路径给 generator 处理
                build_time_info=global_build_time_cn
            )

        # 4. 生成 404.html (如果存在 404.md)
        e404_md_path = os.path.join(config.POSTS_DIR, '404.md')
        if os.path.exists(e404_md_path):
            e404_data = get_metadata_and_content(e404_md_path, '404.html')
            # 404 页面不使用 directory style，保留 404.html
            output_path = os.path.join(config.BUILD_DIR, '404.html')
            template = generator.env.get_template('base.html')
            context = {
                'page_id': '404',
                'page_title': '页面不存在',
                'blog_title': config.BLOG_TITLE,
                'blog_description': config.BLOG_DESCRIPTION,
                'blog_author': config.BLOG_AUTHOR,
                'content_html': e404_data['content_html'], 
                'site_root': generator.get_site_root_prefix(),
                'current_year': datetime.now().year,
                'css_filename': config.CSS_FILENAME,
                'canonical_url': f"{config.BASE_URL.rstrip('/')}{generator.make_internal_url('/404')}",
                'footer_time_info': global_build_time_cn,
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(template.render(context))
            print("Generated: 404.html")
        
        # 5. 生成 Sitemap 和 RSS
        with open(os.path.join(config.BUILD_DIR, config.SITEMAP_FILE), 'w', encoding='utf-8') as f:
            f.write(generator.generate_sitemap(final_parsed_posts))
        print(f"Generated: {config.SITEMAP_FILE}")
            
        with open(os.path.join(config.BUILD_DIR, config.RSS_FILE), 'w', encoding='utf-8') as f:
            f.write(generator.generate_rss(final_parsed_posts))
        print(f"Generated: {config.RSS_FILE}")

    else:
        print("   -> [SKIPPED] Index, Archive, Tags, RSS (No data change)")

    # 6. 复制静态资源 (无增量逻辑，总是复制)
    print("\n[5/5] Copying static assets...")
    shutil.copytree(config.STATIC_DIR, os.path.join(config.BUILD_DIR, config.STATIC_DIR), dirs_exist_ok=True)
    print(f"Copied static assets to {config.BUILD_DIR}/{config.STATIC_DIR}")
    
    # 7. 更新 Manifest (保存完整解析后的数据)
    print("\n[FINAL] Saving build manifest...")
    for post in all_posts:
        post_key = post['link_key'] # 使用 link_key 确保唯一性
        
        # 清理 post 数据，只保留必要的元数据
        data_to_save = {
            'title': post['title'],
            'link': post['link'], # 保存带 .html 的原始 link，因为它是 key
            'date_str': post['date'].strftime('%Y-%m-%d'),
            # 导航信息不需要保存，每次都会重建
            'excerpt': post.get('excerpt', ''),
            'tags': post.get('tags', []),
        }
        # 将解析后的数据和哈希值保存到新的 manifest
        new_manifest['posts'][post_key].update(data_to_save)
        
    save_manifest(new_manifest)
    print("Build complete.")


if __name__ == '__main__':
    main()
