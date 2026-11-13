#!/usr/bin/env python3
"""Static blog generator (stdlib only).

Workflow:
  1. jim sends article text/images to Mica in chat.
  2. Mica saves it as posts/YYYY-MM-DD-slug.md (front matter + markdown body).
  3. Run: python3 build.py   -> regenerates dist/
  4. Publish dist/ as a static web artifact (needs jim's confirmation each time).

Post front matter:
    ---
    title: 文章标题
    date: 2026-10-08
    category: 读书笔记
    tags: 标签1, 标签2
    excerpt: 一句话摘要（可选，不写则自动取正文前 80 字）
    ---
"""

import html
import json
import re
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "posts"
DIST = ROOT / "dist"

# ---- site config (edit freely) ----
SITE_NAME = "纸间集"
SITE_SUBTITLE = ""
SITE_AUTHOR = "jim"
SITE_PASSWORD = "7777777"  # client-side gate for the published site ('' = no gate)
EXCLUDE_SLUGS = {"2026-10-08-hello", "2026-10-11-roundtrip"}  # sandbox test posts, hidden from site
# Media: all uploads (images/videos/audio) served from Cloudflare R2 public dev URL,
# so the site survives origin-server retirement. Replace with a custom domain later if desired.
R2_PUBLIC_BASE = "https://pub-41b05fbcbd534ed283ae185f40bb29da.r2.dev"
OLD_UPLOAD_HOST = "http://3.146.54.178/wp-content/uploads/"


# ---------- tiny markdown -> html (stdlib only) ----------

def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img alt="\1" src="\2" loading="lazy">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def markdown_to_html(src: str) -> str:
    lines = src.split("\n")
    out, i = [], 0
    n = len(lines)

    def flush_para(buf):
        if buf:
            out.append("<p>" + " ".join(_inline(l.strip()) for l in buf) + "</p>")
            buf.clear()

    para = []
    while i < n:
        line = lines[i]
        s = line.strip()
        if line.startswith("```"):
            flush_para(para)
            lang = line[3:].strip()
            code = []
            i += 1
            while i < n and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            cls = f' class="language-{html.escape(lang)}"' if lang else ""
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(code))}</code></pre>")
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush_para(para)
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
        elif s in ("---", "***"):
            flush_para(para)
            out.append("<hr>")
        elif s.startswith(">"):
            flush_para(para)
            quote = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            out.append("<blockquote>" + " ".join(_inline(q) for q in quote) + "</blockquote>")
            continue
        elif re.match(r"^(\d+)[.)]\s+", s):
            flush_para(para)
            items = []
            while i < n and re.match(r"^(\d+)[.)]\s+", lines[i].strip()):
                items.append(re.sub(r"^(\d+)[.)]\s+", "", lines[i].strip()))
                i += 1
            out.append("<ol>" + "".join(f"<li>{_inline(t)}</li>" for t in items) + "</ol>")
            continue
        elif re.match(r"^[-*+]\s+", s):
            flush_para(para)
            items = []
            while i < n and re.match(r"^[-*+]\s+", lines[i].strip()):
                items.append(re.sub(r"^[-*+]\s+", "", lines[i].strip()))
                i += 1
            out.append("<ul>" + "".join(f"<li>{_inline(t)}</li>" for t in items) + "</ul>")
            continue
        elif not s:
            flush_para(para)
        else:
            para.append(line)
        i += 1
    flush_para(para)
    return "\n".join(out)


# ---------- posts ----------

def parse_post(path: Path):
    text = path.read_text(encoding="utf-8")
    meta = {"title": path.stem, "date": str(date.today()), "category": "未分类", "tags": "", "excerpt": ""}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for line in text[3:end].split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip().strip('"').strip("'")
            body = text[end + 4:].lstrip("\n")
    slug = path.stem
    if not meta["excerpt"]:
        # drop embedded media markup, keep link text, then strip any raw URLs
        plain = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body)
        plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", plain)
        plain = re.sub(r"https?://\S+", "", plain)
        plain = re.sub(r"[#>*`\-!\[\]()]", "", plain).strip().replace("\n", " ")
        plain = re.sub(r"\s+", " ", plain).strip()
        meta["excerpt"] = plain[:80] + ("…" if len(plain) > 80 else "")
    else:
        # front-matter excerpts from the old converter may contain raw URLs - hide them
        meta["excerpt"] = re.sub(r"\s*https?://\S+", "", meta["excerpt"]).strip()
    return {"slug": slug, "meta": meta, "html": markdown_to_html(body)}


CSS = """
:root{--bg:#F4F5F9;--surface:#FFF;--ink:#3B4A68;--head:#32325D;--muted:#8898AA;--line:#E9EDF5;
--accent:#5E72E4;--accent2:#8965E0;--chip:rgba(94,114,228,.12);--radius:12px;
--shadow:0 4px 6px rgba(50,50,93,.11),0 1px 3px rgba(0,0,0,.08)}
@media (prefers-color-scheme:dark){:root{--bg:#14161C;--surface:#1E222B;--ink:#C9CFDE;--head:#E6E9F2;
--muted:#8B94A8;--line:#2B303C;--accent:#8B9BF2;--accent2:#A48BF0;--chip:rgba(139,155,242,.16);
--shadow:0 4px 6px rgba(0,0,0,.25),0 1px 3px rgba(0,0,0,.18)}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei","Noto Sans SC",sans-serif;line-height:1.75}
.wrap{max-width:820px;margin:0 auto;padding:0 20px}
.topbar{position:sticky;top:0;z-index:10;background:var(--surface);box-shadow:0 1px 4px rgba(50,50,93,.12)}
.topbar .wrap{display:flex;align-items:center;justify-content:space-between;height:60px}
.brand{font-weight:900;font-size:20px;color:var(--head);text-decoration:none}
.brand::before{content:'';display:inline-block;width:10px;height:10px;border-radius:50%;
background:var(--accent);margin-right:9px;vertical-align:2px}
.brand small{font-weight:400;color:var(--muted);font-size:13px;margin-left:8px}
.nav{font-size:14px}
.nav a{color:var(--muted);text-decoration:none;margin-left:16px}
.nav a:hover{color:var(--accent)}
.banner{background:linear-gradient(135deg,var(--accent),var(--accent2));border-radius:var(--radius);
color:#fff;padding:34px 30px;margin:20px 0 6px;box-shadow:var(--shadow)}
.banner h1{font-size:30px;font-weight:900;margin:0 0 6px;color:#fff}
.banner p{margin:0;opacity:.92;font-size:15px}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}
input.search{flex:1;min-width:200px;padding:10px 16px;border:1px solid var(--line);
border-radius:999px;background:var(--surface);color:var(--ink);font-size:14px;outline:none}
input.search:focus{border-color:var(--accent)}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:6px}
.chips.collapsed{max-height:112px;overflow:hidden}
.chips-toggle{margin:2px 0 10px;padding:5px 16px;border-radius:999px;border:1px solid var(--line);
background:var(--surface);color:var(--accent);font-size:13px;cursor:pointer}
.chips-toggle:hover{border-color:var(--accent)}
.chip{padding:6px 16px;border-radius:999px;background:var(--surface);font-size:14px;cursor:pointer;
border:1px solid var(--line);color:var(--muted)}
.chip.on{background:var(--accent);border-color:var(--accent);color:#fff}
.card{display:block;background:var(--surface);border-radius:var(--radius);box-shadow:var(--shadow);
padding:20px 24px;margin:16px 0;text-decoration:none;color:inherit;
transition:transform .15s ease,box-shadow .15s ease}
.card:hover{transform:translateY(-2px);box-shadow:0 7px 14px rgba(50,50,93,.15),0 3px 6px rgba(0,0,0,.1)}
.card .meta{font-size:12px;color:var(--muted);display:flex;gap:10px;align-items:center;margin-bottom:8px;flex-wrap:wrap}
.card h2{font-size:20px;font-weight:700;margin:0 0 6px;color:var(--head)}
.card:hover h2{color:var(--accent)}
.card p{font-size:15px;color:var(--muted);margin:0}
.tag{font-size:12px;background:var(--chip);border-radius:999px;padding:2px 11px;color:var(--accent)}
.empty{color:var(--muted);text-align:center;padding:40px 0}
footer{color:var(--muted);font-size:13px;text-align:center;padding:34px 0 44px}
article.post{background:var(--surface);border-radius:var(--radius);box-shadow:var(--shadow);
padding:34px 38px;margin:26px 0;font-size:18px;line-height:1.85}
@media(max-width:640px){article.post{padding:24px 20px;font-size:17.5px}.banner{padding:26px 22px}}
.post h1{font-size:29px;font-weight:900;color:var(--head);margin:0 0 8px;line-height:1.35}
.post .meta{color:var(--muted);font-size:14px;margin-bottom:20px;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.post h2{font-size:22px;font-weight:700;color:var(--head);margin:30px 0 10px;
padding-left:12px;border-left:4px solid var(--accent);line-height:1.4}
.post h3{font-size:18.5px;font-weight:700;color:var(--head);margin:24px 0 8px}
.post img{max-width:100%;border-radius:8px;box-shadow:var(--shadow)}
.post blockquote{border-left:3px solid var(--accent);background:var(--chip);margin:18px 0;
padding:12px 18px;border-radius:0 8px 8px 0;color:var(--ink)}
.post pre{background:#242A38;color:#E6E9F2;padding:16px;border-radius:10px;overflow:auto}
.post code{font-family:ui-monospace,Menlo,monospace;font-size:.9em;background:var(--chip);
padding:1px 6px;border-radius:6px;color:var(--accent)}
.post pre code{background:none;padding:0;color:inherit}
.post a{color:var(--accent);text-decoration:none;border-bottom:1px solid rgba(94,114,228,.35)}
.post a:hover{border-bottom-color:var(--accent)}
.back{display:inline-block;margin:6px 0 0;font-size:14px;color:var(--muted);text-decoration:none}
.back:hover{color:var(--accent)}
.gate-ov{position:fixed;inset:0;background:var(--bg);z-index:9999;display:flex;align-items:center;justify-content:center}
.gate-box{background:var(--surface);border-radius:12px;box-shadow:var(--shadow);padding:30px;width:min(360px,86vw);text-align:center}
.gate-box h1{font-size:20px;font-weight:900;color:var(--head);margin:0 0 6px}
.gate-box p{font-size:13px;color:var(--muted);margin:0 0 18px}
.gate-box input{width:100%;padding:12px 14px;border:1px solid var(--line);border-radius:8px;font-size:16px;outline:none;background:var(--bg);color:var(--ink)}
.gate-box input:focus{border-color:var(--accent)}
.gate-box button{width:100%;margin-top:12px;padding:12px;border:0;border-radius:8px;background:var(--accent);color:#fff;font-size:16px;cursor:pointer}
.gate-box .err{color:#c0392b;font-size:13px;margin-top:10px;min-height:1em}
.read-tools{position:fixed;left:14px;bottom:14px;z-index:900;display:flex;flex-direction:column;gap:6px}
.read-tools button{width:46px;height:40px;border-radius:10px;border:1px solid var(--line);background:var(--surface);
color:var(--accent);font-weight:700;font-size:14px;cursor:pointer;box-shadow:var(--shadow)}
.read-tools button:hover{border-color:var(--accent)}
.read-tools button.on{background:var(--accent);border-color:var(--accent);color:#fff}
"""

INDEX_TMPL = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{site}</title>
<style>{css}</style></head>
<body>
<div class="gate-ov" id="gate-ov" style="display:none">
<div class="gate-box">
<h1>{site}</h1>
<p>请输入访问口令</p>
<input type="password" id="gate-pwd" placeholder="请输入口令">
<button id="gate-go">进入</button>
<div class="err" id="gate-err"></div>
</div>
</div>
<script>
(function(){{
var PWD="{pwd}";
var ov=document.getElementById("gate-ov");
try{{
var u=new URL(location.href);
var p=u.searchParams.get("password");
if(p!==null){{
if(p===PWD){{try{{localStorage.setItem("gdst_gate","1")}}catch(e){{}}}}
u.searchParams.delete("password");
history.replaceState(null,"",u.pathname+u.search+u.hash);
}}
}}catch(e){{}}
var ok=false;
try{{ok=localStorage.getItem("gdst_gate")==="1"}}catch(e){{}}
if(ok){{return;}}
ov.style.display="flex";
document.getElementById("gate-go").addEventListener("click",go);
document.getElementById("gate-pwd").addEventListener("keydown",function(e){{if(e.key==="Enter"){{go();}}}});
function go(){{
var v=document.getElementById("gate-pwd").value;
var err=document.getElementById("gate-err");
if(v===PWD){{try{{localStorage.setItem("gdst_gate","1")}}catch(e){{}}ov.style.display="none";}}
else{{err.textContent="口令不正确";}}
}}
}})();
</script>
<header class="topbar"><div class="wrap">
<div class="brand">{site}{brand_small}</div>
<nav class="nav"><a href="index.html">首页</a></nav>
</div></header>
<main class="wrap">
<div class="banner"><h1>{site}</h1><p>{subline}</p></div>
<div class="toolbar">
<input class="search" id="q" placeholder="搜索标题、摘要、标签…">
</div>
<div class="chips" id="chips"></div>
<div id="list"></div>
<div class="empty" id="empty" hidden>没有找到匹配的文章</div>
</main>
<footer>© {year} · 静态博客</footer>
<script>
const POSTS={posts_json};
const chips=document.getElementById('chips'),list=document.getElementById('list'),
q=document.getElementById('q'),empty=document.getElementById('empty');
const cats=['全部',...new Set(POSTS.map(p=>p.category))];
let cur='全部';
cats.forEach(c=>{{const b=document.createElement('button');b.className='chip'+(c==='全部'?' on':'');
b.textContent=c;b.onclick=()=>{{cur=c;document.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));
b.classList.add('on');render()}};chips.appendChild(b)}});
const tgl=document.createElement('button');tgl.className='chips-toggle';tgl.textContent='展开全部分类';
tgl.style.display='none';chips.after(tgl);
chips.classList.add('collapsed');
function chipsOverflow(){{if(chips.scrollHeight>chips.clientHeight+4){{tgl.style.display='inline-block'}}
else{{tgl.style.display='none';chips.classList.remove('collapsed')}}}}
tgl.onclick=()=>{{const c=chips.classList.toggle('collapsed');
tgl.textContent=c?'展开全部分类':'收起分类'}};
window.addEventListener('resize',chipsOverflow);chipsOverflow();
function render(){{const kw=q.value.trim().toLowerCase();
const items=POSTS.filter(p=>(cur==='全部'||p.category===cur)&&
(!kw||(p.title+p.excerpt+p.tags.join(' ')).toLowerCase().includes(kw)));
list.innerHTML=items.map(p=>`<a class="card" href="posts/${{p.slug}}.html">
<div class="meta"><span>${{p.date}}</span><span>${{p.category}}</span>
${{p.tags.map(t=>'<span class="tag">'+t+'</span>').join('')}}</div>
<h2>${{p.title}}</h2><p>${{p.excerpt}}</p></a>`).join('');
empty.hidden=items.length>0}}
q.oninput=render;render();
</script></body></html>"""

POST_TMPL = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{title} · {site}</title>
<style>{css}</style></head>
<body>
<div class="gate-ov" id="gate-ov" style="display:none">
<div class="gate-box">
<h1>{site}</h1>
<p>请输入访问口令</p>
<input type="password" id="gate-pwd" placeholder="请输入口令">
<button id="gate-go">进入</button>
<div class="err" id="gate-err"></div>
</div>
</div>
<script>
(function(){{
var PWD="{pwd}";
var ov=document.getElementById("gate-ov");
try{{
var u=new URL(location.href);
var p=u.searchParams.get("password");
if(p!==null){{
if(p===PWD){{try{{localStorage.setItem("gdst_gate","1")}}catch(e){{}}}}
u.searchParams.delete("password");
history.replaceState(null,"",u.pathname+u.search+u.hash);
}}
}}catch(e){{}}
var ok=false;
try{{ok=localStorage.getItem("gdst_gate")==="1"}}catch(e){{}}
if(ok){{return;}}
ov.style.display="flex";
document.getElementById("gate-go").addEventListener("click",go);
document.getElementById("gate-pwd").addEventListener("keydown",function(e){{if(e.key==="Enter"){{go();}}}});
function go(){{
var v=document.getElementById("gate-pwd").value;
var err=document.getElementById("gate-err");
if(v===PWD){{try{{localStorage.setItem("gdst_gate","1")}}catch(e){{}}ov.style.display="none";}}
else{{err.textContent="口令不正确";}}
}}
}})();
</script>
<header class="topbar"><div class="wrap">
<div class="brand"><a href="../index.html" style="text-decoration:none;color:inherit">{site}{brand_small}</a></div>
<nav class="nav"><a href="../index.html">首页</a></nav>
</div></header>
<main class="wrap">
<a class="back" href="../index.html">← 返回首页</a>
<article class="post">
<h1>{title}</h1>
<div class="meta"><span>{date}</span><span>{category}</span>{tags}</div>
{body}
</article>
<a class="back" href="../index.html">← 返回首页</a>
</main>
<div class="read-tools">
<button id="rt-plus" title="增大字号">A+</button>
<button id="rt-minus" title="减小字号">A-</button>
<button id="rt-bold" title="加粗开关">B</button>
</div>
<footer>© {year} · 静态博客</footer>
<script>
(function(){{
var KEY_FS="muse_fs",KEY_B="muse_fb";
var art=document.querySelector("article.post");
if(!art){{return;}}
var fs=parseFloat(localStorage.getItem(KEY_FS))||18;
var bold=localStorage.getItem(KEY_B)==="1";
function apply(){{art.style.fontSize=fs+"px";art.style.fontWeight=bold?"600":"";}}
function save(){{localStorage.setItem(KEY_FS,fs);localStorage.setItem(KEY_B,bold?"1":"0");}}
var bb=document.getElementById("rt-bold");
function paint(){{bb.classList.toggle("on",bold)}}
bb.addEventListener("click",function(){{bold=!bold;apply();save();paint();}});
paint();
document.getElementById("rt-plus").addEventListener("click",function(){{fs=Math.min(26,fs+2);apply();save();}});
document.getElementById("rt-minus").addEventListener("click",function(){{fs=Math.max(14,fs-2);apply();save();}});
apply();
}})();
</script>
</body></html>"""


def rewrite_media(body):
    """Point all wp-content/uploads media (images/videos/audio) at the R2 public URL."""
    if not R2_PUBLIC_BASE:
        return body
    new = R2_PUBLIC_BASE + "/uploads/"

    def _fix(m):
        url = m.group(0)
        return new + url[len(OLD_UPLOAD_HOST):]

    return re.sub(re.escape(OLD_UPLOAD_HOST) + r"[^\s\"'<>]+", _fix, body)


def build():
    posts = sorted(
        (parse_post(p) for p in POSTS_DIR.glob("*.md") if p.stem not in EXCLUDE_SLUGS),
        key=lambda p: p["meta"]["date"], reverse=True,
    )
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "posts").mkdir(parents=True)

    index_data = [{
        "slug": p["slug"], "title": p["meta"]["title"], "date": p["meta"]["date"],
        "category": p["meta"]["category"],
        "tags": [t.strip() for t in p["meta"]["tags"].split(",") if t.strip()],
        "excerpt": p["meta"]["excerpt"],
    } for p in posts]

    brand_small = ("<small>" + html.escape(SITE_SUBTITLE) + "</small>") if SITE_SUBTITLE else ""
    subline = ((html.escape(SITE_SUBTITLE) + " · ") if SITE_SUBTITLE else "") + f"共 {len(posts)} 篇"

    (DIST / "index.html").write_text(INDEX_TMPL.format(
        site=html.escape(SITE_NAME), brand_small=brand_small, subline=subline,
        author=html.escape(SITE_AUTHOR), count=len(posts),
        year=date.today().year, css=CSS, pwd=html.escape(SITE_PASSWORD, quote=True),
        posts_json=json.dumps(index_data, ensure_ascii=False),
    ), encoding="utf-8")

    for p in posts:
        m = p["meta"]
        tags = "".join(f'<span class="tag">{html.escape(t.strip())}</span>'
                       for t in m["tags"].split(",") if t.strip())
        (DIST / "posts" / f'{p["slug"]}.html').write_text(POST_TMPL.format(
            title=html.escape(m["title"]), site=html.escape(SITE_NAME),
            brand_small=brand_small,
            author=html.escape(SITE_AUTHOR), year=date.today().year,
            date=html.escape(m["date"]), category=html.escape(m["category"]),
            tags=tags, body=rewrite_media(p["html"]), css=CSS, pwd=html.escape(SITE_PASSWORD, quote=True),
        ), encoding="utf-8")

    print(f"built {len(posts)} posts -> {DIST}")


if __name__ == "__main__":
    build()
