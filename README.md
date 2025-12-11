# Scaling Parakeet (Minimalist Python SSG)

> 一个极简、高性能、纯 Python 驱动的静态网站生成器。

本项目是一个定制化的静态站点生成器（Static Site Generator），专为追求极致性能、极简主义设计和完全掌控代码的开发者打造。它不依赖庞大的前端框架（如 React/Vue/Hugo/Hexo），仅使用 Python 标准库及少量核心依赖（Markdown, Jinja2）即可将 Markdown 文档转化为优雅的静态 HTML 网站。

## ✨ 核心特性

*   **⚡️ 极速与增量构建**：内置智能构建系统 (`autobuild.py`)，通过文件哈希 (`SHA256`) 和修改时间检测变化，仅重新生成变动的内容，毫秒级完成构建。
*   **🎨 优雅的极简设计**：
    *   **自动暗色模式**：完全适配系统深色/浅色主题。
    *   **响应式布局**：完美适配移动端（包含移动端折叠目录、表格横向滚动优化）。
    *   **排版优化**：针对中文阅读优化的行高与字间距，解决了移动端标题错行问题。
    *   **代码高亮**：集成 Pygments，提供 Mac 窗口风格的代码块与多语言高亮。
*   **🛠️ 纯 Python 驱动**：逻辑清晰，易于修改。没有复杂的 `node_modules` 黑洞。
*   **🔍 SEO 友好**：自动生成 `sitemap.xml`、`rss.xml` 以及 JSON-LD 结构化数据（Schema.org），不仅让搜索引擎喜欢，还支持 RSS 订阅。
*   **🚀 GitHub Pages 自动化**：内置 GitHub Actions 工作流，推送代码即自动构建并部署。

## 📂 项目结构

```text
.
├── autobuild.py        # [核心] 构建脚本，处理增量逻辑、文件哈希和流程控制
├── parser.py           # Markdown 解析器，处理 Frontmatter、Slug 和 HTML 后处理
├── generator.py        # HTML 生成器，利用 Jinja2 渲染页面、RSS 和 Sitemap
├── config.py           # 全局配置文件（站点信息、路径、Markdown 扩展配置）
├── requirements.txt    # Python 依赖列表
├── markdown/           # [源文件] 存放你的 Markdown 文章 (.md)
├── templates/          # Jinja2 模板文件 (base.html)
├── assets/             # 静态资源 (CSS, 图片等)
├── .github/            # GitHub Actions 自动化部署配置
└── _site/              # [构建产物] 生成的静态网站 (自动生成，勿手动修改)
```

## 🚀 快速开始

### 1. 环境准备

确保你的电脑上安装了 Python 3.x。

```bash
# 克隆仓库
git clone https://github.com/your-username/scaling-parakeet-main.git
cd scaling-parakeet-main

# 创建并激活虚拟环境 (推荐)
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 本地构建

运行自动构建脚本：

```bash
python autobuild.py
```

构建完成后，生成的网站文件位于 `_site/` 目录下。你可以使用 Python 自带的服务器进行预览：

```bash
cd _site
python -m http.server 8000
# 访问 http://localhost:8000
```

### 3. 撰写文章

在 `markdown/` 目录下创建一个新的 `.md` 文件。文件头部必须包含 YAML Frontmatter 元数据：

```yaml
---
title: 我的第一篇文章
date: 2025-12-12
slug: my-first-post  # 可选，默认使用文件名
tags: [生活, 编程]    # 标签
summary: 这是一段文章摘要，会显示在列表页和 SEO 描述中。
hidden: false        # 设置为 true 可隐藏文章（仅通过直接链接访问）
status: published    # 设置为 draft 可标记为草稿
---

## 正文开始

这里支持 **Markdown** 语法。

```python
print("Hello World")
```
```

## ⚙️ 配置与自定义

所有核心配置均位于 `config.py` 文件中：

*   **站点信息**：修改 `BLOG_TITLE`, `BLOG_author`, `BASE_URL` 等。
*   **Markdown 扩展**：可以在 `MARKDOWN_EXTENSIONS` 列表中启用或禁用插件（如脚注、数学公式、任务列表等）。
*   **构建路径**：自定义输入/输出目录。

样式文件位于 `assets/style.css`。构建脚本会自动检测 CSS 文件的变化，并强制触发全量样式的更新。

## 📦 部署到 GitHub Pages

本项目已配置好 GitHub Actions (`.github/workflows/autobuild.yml`)。

1.  将代码推送到 GitHub 仓库。
2.  进入仓库 Settings -> **Pages**。
3.  在 "Build and deployment" 下，Source 选择 **GitHub Actions**。
4.  之后每次 `git push` 到 `main` 分支，Action 会自动运行：
    *   安装依赖。
    *   检查增量变化（利用 `.build_manifest.json`）。
    *   生成静态文件。
    *   发布到 GitHub Pages。

### 关于自定义域名

如果需要使用自定义域名：
1.  修改 `CNAME` 文件中的域名。
2.  构建脚本会自动将其复制到 `_site` 目录。
3.  在 GitHub Pages 设置中绑定该域名。

## 🧠 技术细节

*   **增量构建原理**：脚本会维护一个 `.build_manifest.json` 文件，记录每篇文章、模板文件和 CSS 的 SHA256 哈希值。构建时会对比哈希值，仅重新渲染内容发生变化的文章。
*   **HTML 后处理**：`parser.py` 使用 BeautifulSoup 对生成的 HTML 进行优化，例如为所有表格添加滚动容器 (`.table-wrapper`)，为图片添加懒加载属性 (`loading="lazy"`)。
*   **CSS 架构**：使用 CSS 变量 (`var(--color-...)`) 实现高效的明暗主题切换，不依赖 JavaScript 进行样式计算，避免页面闪烁 (FOUC)。

## 📄 许可证

本项目代码可自由使用（MIT License）。
生成的内容版权请遵循 `base.html` 页脚中的声明（默认为 CC BY-NC 4.0）。
