#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 扫描 posts/ 和 projects/，自动生成 content.json。
# ★ 你不需要手动编辑 content.json，它是机器生成的。你只管往文件夹里放文件。
# 无第三方依赖，只用 Python 标准库。

import os, re, json
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def parse_front_matter(text):
    """解析文件开头可选的 --- ... --- 元信息块，返回 (meta, body)。"""
    meta, body = {}, text
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if m:
        block, body = m.group(1), m.group(2)
        current_key = None
        for line in block.splitlines():
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith("#"):
                continue
            # 支持 YAML 列表格式 (例如 - tag)
            if line_stripped.startswith("-") and current_key:
                val = line_stripped[1:].strip().strip("\"'")
                if not isinstance(meta.get(current_key), list):
                    meta[current_key] = []
                meta[current_key].append(val)
                continue
            if ":" in line_stripped:
                key, val = line_stripped.split(":", 1)
                key, val = key.strip(), val.strip()
                current_key = key
                if val.startswith("[") and val.endswith("]"):       # tags: [a, b, c]
                    meta[key] = [x.strip().strip("\"'") for x in val[1:-1].split(",") if x.strip()]
                elif val == "":
                    meta[key] = []
                else:
                    meta[key] = val.strip("\"'")
    return meta, body


def first_paragraph(body):
    """没写 summary 时，自动取正文第一段做摘要。"""
    for block in re.split(r"\n\s*\n", body.strip()):
        block = block.strip()
        if not block or block.startswith("#") or block.startswith("```"):
            continue
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", block)   # 去链接
        text = re.sub(r"[`*_>#$\\]", "", text)                  # 去常见 markdown 符号
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            return text[:80] + ("…" if len(text) > 80 else "")
    return ""


def prettify(slug):
    return slug.replace("-", " ").replace("_", " ").strip()


def file_date(path):
    return datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


# ---------- 扫描随笔 ----------
posts = []
posts_dir = os.path.join(ROOT, "posts")
if os.path.isdir(posts_dir):
    for fn in os.listdir(posts_dir):
        if not fn.endswith(".md"):
            continue
        path = os.path.join(posts_dir, fn)
        meta, body = parse_front_matter(read(path))
        slug = fn[:-3]

        # 日期优先级：front matter > 文件名前缀 YYYY-MM-DD- > 文件修改时间
        d = meta.get("date")
        if not d:
            m = re.match(r"(\d{4}-\d{2}-\d{2})[-_]", slug)
            d = m.group(1) if m else file_date(path)

        # 演示链接优先级：front matter > 同名 projects/<slug>/index.html 自动关联
        demo = meta.get("demo")
        if not demo and os.path.isfile(os.path.join(ROOT, "projects", slug, "index.html")):
            demo = "projects/%s/index.html" % slug

        posts.append({
            "slug": slug,
            "title": meta.get("title") or prettify(slug),
            "date": d,
            "tags": meta.get("tags") or [],
            "summary": meta.get("summary") or first_paragraph(body),
            "demo": demo,
        })
posts.sort(key=lambda p: p.get("date", ""), reverse=True)

# ---------- 扫描独立作品（未与随笔同名关联的 projects 子文件夹） ----------
paired = {p["demo"] for p in posts if p.get("demo")}
projects = []
projects_dir = os.path.join(ROOT, "projects")
if os.path.isdir(projects_dir):
    for name in sorted(os.listdir(projects_dir)):
        index = os.path.join(projects_dir, name, "index.html")
        if not os.path.isfile(index):
            continue
        rel = "projects/%s/index.html" % name
        if rel in paired:
            continue   # 已通过对应随笔展示，不重复
        title = None
        mt = re.search(r"<title[^>]*>(.*?)</title>", read(index), re.S | re.I)
        if mt:
            title = re.sub(r"\s+", " ", mt.group(1)).strip()
        projects.append({"title": title or prettify(name), "path": rel})

# ---------- 站点信息（你手动维护的 site.json，不会被覆盖） ----------
site = {}
site_path = os.path.join(ROOT, "site.json")
if os.path.isfile(site_path):
    try:
        site = json.loads(read(site_path))
    except Exception as e:
        print("[warning] site.json 解析失败，已忽略：", e)

# ---------- 写出 content.json ----------
out = {"site": site, "posts": posts, "projects": projects}
with open(os.path.join(ROOT, "content.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print("已生成 content.json：%d 篇随笔，%d 个独立作品" % (len(posts), len(projects)))
