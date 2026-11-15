# -*- coding: utf-8 -*-
"""Render the briefing as HTML, Markdown, XLSX, an archive page, and email HTML."""
from __future__ import annotations

import html as html_lib
import os
import re
from datetime import datetime
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .sources import LEAN_BUCKET, LEAN_DESC, LEANS

CATS = [
    ("政治", "politics", "01", "POLITICS", "#a4261d"),
    ("经济", "economy", "02", "ECONOMY", "#1f5c4d"),
    ("F1", "f1", "03", "FORMULA 1", "#a15c12"),
    ("AI", "ai", "04", "ARTIFICIAL INTELLIGENCE", "#1e4b8f"),
]
BADGE = {
    "左": "b-left", "中左": "b-cl", "中": "b-c", "中右": "b-cr",
    "右": "b-r", "官媒": "b-state", "专业": "b-pro", "一手": "b-primary",
    "未评级": "b-other",
}


def esc(value) -> str:
    return html_lib.escape(str(value or ""), quote=True)


def badge_class(lean: str) -> str:
    return BADGE.get(lean, "b-other")


def day_cn(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return date_str
    week = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][d.weekday()]
    return f"{d.year}年{d.month}月{d.day}日 {week}"


def all_sources(data: dict) -> list[dict]:
    return [s for story in data.get("stories", []) for s in story.get("sources", [])]


def lean_mix(data: dict) -> dict[str, int]:
    mix = {lean: 0 for lean in LEANS}
    mix["未评级"] = 0
    for src in all_sources(data):
        mix[src.get("lean", "未评级")] = mix.get(src.get("lean", "未评级"), 0) + 1
    return mix


def mix_text(data: dict) -> str:
    mix = lean_mix(data)
    order = LEANS + ["未评级"]
    return " · ".join(f"{k} {mix[k]}" for k in order if mix.get(k))


def extract_numbers(text: str, limit: int = 3) -> str:
    # Do not turn dates ("11月3日") or years ("2026") into "key numbers".
    pattern = (r"(?<![A-Za-z\d.])(?:\$|€|£)?\d+(?:[.,]\d+)*"
               r"(?:%|亿|万亿|bn|billion|million|m|岁|站|km|公里|万人|美元|人|名|起|家|项)?"
               r"(?![\d月日年/])")
    found = []
    for m in re.finditer(pattern, text or ""):
        token = m.group(0).strip(" .,")
        if not token:
            continue
        unit = re.sub(r"^[\$€£]?[\d.,]+", "", token)
        if re.fullmatch(r"(?:19|20)\d{2}", token) and not unit:
            continue
        if token not in found:
            found.append(token)
    def priority(x: str) -> tuple[int, int]:
        has_unit = bool(re.search(r"[%$€£]|亿|万|bn|billion|million|岁|站|km|公里|人|名|起|家|项", x, re.I))
        return (0 if has_unit else 1, -len(x))
    found.sort(key=priority)
    out = found[:limit]
    return " · ".join(out) if out else "—"


def fallback_fields(data: dict) -> dict:
    stories = data.get("stories", [])
    if not data.get("lede"):
        data["lede"] = (
            f"今日由 RSS 多源自动聚合，共 {len(stories)} 条要闻、"
            f"{len(all_sources(data))} 个来源；政治、经济、F1、AI 四条线各自独立成表。"
        )
    if not data.get("takeaways"):
        data["takeaways"] = [
            f"{s['category']}：{s['title']}" for s in stories[:3]
        ] or ["今日抓取到的条目不足，请检查 RSS 源或稍后重跑。"]
    for story in stories:
        if not story.get("facts"):
            story["facts"] = [story.get("title", "")]
        if not story.get("framing"):
            names = " / ".join(s["name"] for s in story.get("sources", []))
            story["framing"] = f"{len(story.get('sources', []))} 家来源：{names}"
        for src in story.get("sources", []):
            if not src.get("angle"):
                src["angle"] = "标题与摘要来自该媒体的 RSS。"
    return data


def render_html(data: dict, css: str, archive_link: bool = True) -> str:
    data = fallback_fields(data)
    date_str = data["date"]
    stories = data.get("stories", [])
    srcs = all_sources(data)
    issues = []
    if not data.get("llm_used"):
        if data.get("translation_used"):
            issues.append("未启用模型摘要；标题、事实与来源角度为机器翻译，数字与人名请以原文链接为准。")
        else:
            issues.append("未启用中文摘要（未配置模型 API 或调用失败），标题与摘要保留英文原文。")
    failed = data.get("stats", {}).get("feeds_failed", 0)
    if failed:
        issues.append(f"{failed} 个 RSS 源抓取失败，已跳过；这会影响当天的来源覆盖。")
    for warning in data.get("warnings", []):
        issues.append(warning)
    notice = ""
    if issues:
        notice = '<div class="notice"><b>自动生成提示</b><ul>' + "".join(f"<li>{esc(x)}</li>" for x in issues) + "</ul></div>"

    glance_rows = []
    for cat, cid, num, en, accent in CATS:
        got = [s for s in stories if s["category"] == cat]
        if not got:
            glance_rows.append(
                f'<tr><td class="cat"><i style="background:{accent}"></i><a href="#{cid}">{esc(cat)}</a></td>'
                f'<td>暂无足够数据</td><td class="num">—</td><td>—</td></tr>'
            )
            continue
        s = got[0]
        nums = extract_numbers(" ".join(s.get("facts", [])))
        src_txt = " / ".join(f'{x["name"]}（{x["lean"]}）' for x in s.get("sources", [])[:3])
        glance_rows.append(
            f'<tr><td class="cat"><i style="background:{accent}"></i><a href="#{cid}">{esc(cat)}</a></td>'
            f'<td>{esc(s["title"])}</td><td class="num">{esc(nums)}</td><td>{esc(src_txt)}</td></tr>'
        )

    sections = []
    for cat, cid, num, en, accent in CATS:
        got = [s for s in stories if s["category"] == cat]
        rows = []
        for s in got:
            facts = "".join(f"<li>{esc(f)}</li>" for f in s.get("facts", []))
            sources = []
            for src in s.get("sources", []):
                angle = f'<span class="angle">{esc(src["angle"])}</span>' if src.get("angle") else ""
                sources.append(
                    f'<div class="src"><a href="{esc(src["url"])}" target="_blank" rel="noopener">{esc(src["name"])}</a>'
                    f'<span class="badge {badge_class(src["lean"])}">{esc(src["lean"])}</span>{angle}</div>'
                )
            rows.append(
                f'<tr><td class="idx">{esc(s["id"])}</td>'
                f'<td><div class="story-title">{esc(s["title"])}</div><div class="story-kicker">{en}</div></td>'
                f'<td class="facts"><ul>{facts}</ul></td>'
                f'<td class="sources">{"".join(sources)}</td>'
                f'<td class="frame">{esc(s.get("framing", ""))}</td></tr>'
            )
        if not rows:
            rows.append('<tr><td colspan="5" class="empty">该板块今天没有聚合到足够条目。检查 RSS 源，或稍后手动重跑。</td></tr>')
        sections.append(
            f'<section class="topic" id="{cid}"><div class="topic-head"><span class="num">{num}</span>'
            f'<h2>{esc(cat)}</h2><span class="en">{en}</span></div>'
            f'<p class="topic-blurb">{esc(section_blurb(cat))}</p>'
            f'<div class="table-wrap"><table class="stories"><thead><tr>'
            f'<th style="width:4%">#</th><th style="width:15%">事件</th><th style="width:31%">核心事实</th>'
            f'<th style="width:33%">来源与倾向</th><th style="width:17%">叙事差异</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></section>'
        )

    takeaways = "".join(f"<li>{esc(x)}</li>" for x in data.get("takeaways", [])[:4])
    archive = '<a href="archive.html">往期存档 →</a>' if archive_link else ""
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>全球要闻简报 · {esc(date_str)}</title>
<style>{css}</style></head><body><div class="page">
<header class="masthead">
  <div class="kicker">DAILY BRIEF · {esc(date_str.replace('-', '.'))} · AUTO</div>
  <h1>全球要闻简报</h1>
  <div class="sub">政治 · 经济 · 一级方程式 · 人工智能</div>
  <div class="meta"><span><b>{len(stories)}</b> 条要闻</span><span><b>{len(srcs)}</b> 个来源</span>
  <span>截至 <b>08:00</b>（Asia/Shanghai）</span><span>模型：<b>{esc(data.get("llm_provider") or "未启用")}</b></span>
  <span>{archive}</span></div>
</header>
{notice}
<p class="lede">{esc(data.get("lede", ""))}</p>
<aside class="takeaways"><div class="tk-head">编辑判断<span>自动生成，不是事实陈述，是可被明天推翻的阅读框架</span></div>
<ol>{takeaways}</ol></aside>
<h2 class="sec">一分钟速览 <small>ONE-MINUTE GLANCE</small></h2>
<table class="glance-table"><thead><tr><th>板块</th><th>今日主线</th><th>关键数字</th><th>来源覆盖</th></tr></thead>
<tbody>{"".join(glance_rows)}</tbody></table>
{"".join(sections)}
<section class="method">
<div><h2>来源与倾向：怎么读</h2>
<p>“倾向”描述媒体的整体编辑立场，参考 AllSides、Ad Fontes 等公开评级与编辑部公开立场做近似归类；它不判定单篇报道真伪，也不等于可信度。</p>
<div class="legend">{"".join(f'<span><i class="badge {badge_class(l)}">{l}</i>{LEAN_DESC[l]}</span>' for l in LEANS + ["未评级"])}</div>
<p>本期来源构成：<b>{esc(mix_text(data))}</b>。每条硬事实尽量保留一个“中”或“一手”来源作锚点；左右来源用于展示同一事实的不同框定。</p>
<p class="fine">自动聚合的覆盖缺口是真实的：如果某板块只有单一来源，表中会标注；不要把“来源少”误读成“事实弱”。</p></div>
<div><h2>制表说明</h2><ul>
<li>时间口径：按 Asia/Shanghai 当日 08:00 前已刊发的 RSS 条目；回溯窗口 48 小时。</li>
<li>聚类：标题词重叠 + 专有名词重叠 + 序列相似度；同一媒体在同一故事中只保留一条。</li>
<li>数字：直接取自各源标题/摘要；未做二次计算，冲突数字并列保留。</li>
<li>生成：GitHub Actions + Python 标准库 + openpyxl；不依赖付费新闻 API。</li>
<li>邮件：如配置了 SMTP/Resend，会发送本页摘要与 XLSX 附件。</li>
</ul><p class="fine">本页为自动生成的研究简报，不构成投资、法律或政治建议。</p></div>
</section>
<div class="footer"><span><b>全球要闻简报</b> · {esc(date_str)}</span>
<span>政治 / 经济 / F1 / AI · {len(srcs)} sources</span>
<span>生成于 {esc(data.get("generated_at", ""))}</span></div>
</div></body></html>"""


def section_blurb(cat: str) -> str:
    return {
        "政治": "选举、司法与外交的交叠地带；同一件事在不同媒体那里常常不是同一件事。",
        "经济": "利率、油价与 AI 资本开支，构成同一张宏观压力表。",
        "F1": "赛季的戏剧性既在赛道，也在采访证、成本帽与车手市场。",
        "AI": "模型、算力与诉讼同时加速；头条背后的估值与监管才是长线。",
    }.get(cat, "")


def render_markdown(data: dict) -> str:
    data = fallback_fields(data)
    lines = [f"# 全球要闻简报 · {data['date']}", "",
             f"> 截至 08:00（Asia/Shanghai）｜{len(data['stories'])} 条要闻｜{len(all_sources(data))} 个来源", "",
             data.get("lede", ""), "", "## 编辑判断", ""]
    for i, t in enumerate(data.get("takeaways", [])[:4], 1):
        lines.append(f"{i}. {t}")
    lines += ["", "## 一分钟速览", "", "| 板块 | 今日主线 | 关键数字 | 来源覆盖 |", "|---|---|---|---|"]
    for cat, cid, num, en, accent in CATS:
        got = [s for s in data["stories"] if s["category"] == cat]
        if not got:
            lines.append(f"| **{cat}** | 暂无足够数据 | — | — |")
            continue
        s = got[0]
        nums = extract_numbers(" ".join(s.get("facts", [])))
        srcs = " / ".join(f'{x["name"]}（{x["lean"]}）' for x in s.get("sources", [])[:3])
        lines.append(f"| **{cat}** | {s['title']} | {nums} | {srcs} |")
    for cat, cid, num, en, accent in CATS:
        lines += ["", f"## {num} {cat} · {en}", "", section_blurb(cat), "",
                  "| # | 事件 | 核心事实 | 来源（倾向） | 叙事差异 |", "|---|---|---|---|---|"]
        got = [s for s in data["stories"] if s["category"] == cat]
        if not got:
            lines.append("| — | 暂无足够数据 | — | — | — |")
            continue
        for s in got:
            facts = "<br>".join(f"• {f}" for f in s.get("facts", []))
            srcs = "<br>".join(
                f'[{x["name"]}]({x["url"]})（{x["lean"]}）— {x["angle"]}' for x in s.get("sources", [])
            )
            lines.append(f"| {s['id']} | **{s['title']}** | {facts} | {srcs} | {s.get('framing', '')} |")
    lines += ["", "## 来源与倾向：怎么读", "",
              "“倾向”描述媒体的整体编辑立场，不判定单篇报道真伪；官媒单列，专业/一手不放进左右轴。", "",
              f"本期来源构成：{mix_text(data)}。", "",
              "> 自动聚合的覆盖缺口是真实的：单一来源条目会在表中标注。", "",
              "---", "", "*本页为自动生成的研究简报，不构成投资、法律或政治建议。*", ""]
    return "\n".join(lines)


def render_email_html(data: dict, pages_url: str = "") -> str:
    data = fallback_fields(data)
    rows = []
    for cat, cid, num, en, accent in CATS:
        got = [s for s in data["stories"] if s["category"] == cat]
        if not got:
            rows.append(f'<tr><td colspan="3" style="padding:10px;color:#888">该板块暂无数据</td></tr>')
            continue
        for s in got:
            facts = "<br>".join(f"• {esc(f)}" for f in s.get("facts", [])[:3])
            srcs = " · ".join(f'{esc(x["name"])}（{esc(x["lean"])}）' for x in s.get("sources", []))
            rows.append(
                f'<tr><td style="padding:10px;border-bottom:1px solid #e5ddd0;vertical-align:top">'
                f'<b>{esc(cat)}</b><br><span style="color:#a4261d;font-size:12px">{esc(s["id"])}</span></td>'
                f'<td style="padding:10px;border-bottom:1px solid #e5ddd0;vertical-align:top">'
                f'<b style="font-size:14px">{esc(s["title"])}</b><br>'
                f'<span style="color:#555;font-size:12px;line-height:1.6">{facts}</span><br>'
                f'<span style="color:#777;font-size:12px">来源：{srcs}</span></td>'
                f'<td style="padding:10px;border-bottom:1px solid #e5ddd0;vertical-align:top;color:#555;font-size:12px">'
                f'{esc(s.get("framing", ""))}</td></tr>'
            )
    button = ""
    if pages_url:
        button = (f'<p style="margin:18px 0"><a href="{esc(pages_url)}" '
                  f'style="background:#181512;color:#fff;padding:10px 16px;text-decoration:none;font-size:13px">'
                  f'阅读网页版 →</a></p>')
    return f"""<!doctype html><html><body style="margin:0;background:#f5f1e8;font-family:-apple-system,'Segoe UI','Microsoft YaHei',sans-serif;color:#181512">
<div style="max-width:860px;margin:0 auto;padding:24px">
<div style="border-top:6px solid #181512;padding-top:14px">
<div style="font:700 10px monospace;letter-spacing:.18em;color:#a4261d">DAILY BRIEF · {esc(data['date'])}</div>
<h1 style="font-size:34px;margin:6px 0;font-family:Georgia,'Songti SC',serif">全球要闻简报</h1>
<div style="color:#666;font-size:13px">政治 · 经济 · F1 · AI ｜ {len(data['stories'])} 条要闻 ｜ {len(all_sources(data))} 个来源</div>
</div>
<p style="font-size:15px;line-height:1.7;margin:18px 0">{esc(data.get('lede',''))}</p>
<table style="width:100%;border-collapse:collapse;background:#fbf8f1;border:1px solid #d9d1c3">
<thead><tr style="background:#181512;color:#fff;font-size:11px;text-align:left">
<th style="padding:8px">板块</th><th style="padding:8px">事件 / 事实 / 来源</th><th style="padding:8px">叙事差异</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
{button}
<p style="color:#666;font-size:12px;line-height:1.7">“倾向”描述媒体整体编辑立场，不判定单篇报道真伪。完整表格、来源链接与往期存档见网页版。<br>
本邮件由 GitHub Actions 自动发送；附件为同日 XLSX。</p>
<p style="color:#999;font-size:11px">生成于 {esc(data.get('generated_at',''))} · 不构成投资、法律或政治建议。</p>
</div></body></html>"""


def write_xlsx(data: dict, path: str) -> None:
    data = fallback_fields(data)
    ink, card, line, red, muted = "181512", "FBF8F1", "D9D1C3", "A4261D", "6B6259"
    cat_fill = {"政治": "F4E3E0", "经济": "E2EFEA", "F1": "F8EBD9", "AI": "E3E9F4"}
    thin = Side(style="thin", color=line)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    hdr_font = Font(name="Microsoft YaHei", bold=True, color="FFFFFF", size=10)
    hdr_fill = PatternFill("solid", fgColor=ink)
    body = Font(name="Microsoft YaHei", size=10, color=ink)
    small = Font(name="Microsoft YaHei", size=9, color=muted)
    wrap = Alignment(wrap_text=True, vertical="top")

    wb = Workbook()
    ws = wb.active
    ws.title = "速览"
    ws.sheet_view.showGridLines = False
    ws.merge_cells("A1:D1")
    ws["A1"] = f"全球要闻简报 · {data['date']}"
    ws["A1"].font = Font(name="Microsoft YaHei", bold=True, size=18, color=ink)
    ws["A1"].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 32
    ws.merge_cells("A2:D2")
    ws["A2"] = f"截至 08:00（Asia/Shanghai）｜{len(data['stories'])} 条要闻｜{len(all_sources(data))} 个来源｜模型：{data.get('llm_provider') or '未启用'}"
    ws["A2"].font = small
    for i, h in enumerate(["板块", "今日主线", "关键数字", "来源覆盖"], 1):
        c = ws.cell(row=4, column=i, value=h)
        c.font, c.fill, c.border = hdr_font, hdr_fill, border
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    r = 5
    for cat, cid, num, en, accent in CATS:
        got = [s for s in data["stories"] if s["category"] == cat]
        if got:
            s = got[0]
            vals = [cat, s["title"], extract_numbers(" ".join(s.get("facts", []))),
                    " / ".join(f'{x["name"]}（{x["lean"]}）' for x in s.get("sources", [])[:3])]
        else:
            vals = [cat, "暂无足够数据", "—", "—"]
        for col, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=col, value=v)
            c.font, c.alignment, c.border = body, wrap, border
            if col == 1:
                c.fill = PatternFill("solid", fgColor=cat_fill[cat])
        ws.row_dimensions[r].height = 40
        r += 1
    for col, w in zip("ABCD", [10, 78, 26, 50]):
        ws.column_dimensions[col].width = w

    ws2 = wb.create_sheet("要闻明细")
    ws2.sheet_view.showGridLines = False
    cols = ["日期", "类别", "编号", "事件", "核心事实", "来源与倾向", "叙事差异", "来源数"]
    widths = [11, 8, 8, 34, 72, 44, 38, 7]
    for i, (h, w) in enumerate(zip(cols, widths), 1):
        c = ws2.cell(row=1, column=i, value=h)
        c.font, c.fill, c.border = hdr_font, hdr_fill, border
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws2.column_dimensions[get_column_letter(i)].width = w
    ws2.freeze_panes = "A2"
    ws2.auto_filter.ref = f"A1:H{max(2, len(data['stories']) + 1)}"
    for idx, s in enumerate(data["stories"], 2):
        facts = "\n".join(f"{i+1}. {f}" for i, f in enumerate(s.get("facts", [])))
        srcs = "；".join(f'{x["name"]}（{x["lean"]}）' for x in s.get("sources", []))
        vals = [data["date"], s["category"], s["id"], s["title"], facts, srcs, s.get("framing", ""), len(s.get("sources", []))]
        for col, v in enumerate(vals, 1):
            c = ws2.cell(row=idx, column=col, value=v)
            c.font, c.alignment, c.border = body, wrap, border
        ws2.cell(row=idx, column=2).fill = PatternFill("solid", fgColor=cat_fill[s["category"]])
        ws2.row_dimensions[idx].height = 100

    ws3 = wb.create_sheet("来源明细")
    ws3.sheet_view.showGridLines = False
    cols = ["日期", "类别", "编号", "事件", "来源", "倾向", "报道角度", "链接"]
    widths = [11, 8, 8, 34, 26, 8, 52, 58]
    for i, (h, w) in enumerate(zip(cols, widths), 1):
        c = ws3.cell(row=1, column=i, value=h)
        c.font, c.fill, c.border = hdr_font, hdr_fill, border
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws3.column_dimensions[get_column_letter(i)].width = w
    ws3.freeze_panes = "A2"
    ws3.auto_filter.ref = f"A1:H{max(2, len(all_sources(data)) + 1)}"
    r = 2
    for s in data["stories"]:
        for x in s.get("sources", []):
            vals = [data["date"], s["category"], s["id"], s["title"], x["name"], x["lean"],
                    x.get("angle", ""), x.get("url", "")]
            for col, v in enumerate(vals, 1):
                c = ws3.cell(row=r, column=col, value=v)
                c.font, c.alignment, c.border = body, wrap, border
            ws3.cell(row=r, column=2).fill = PatternFill("solid", fgColor=cat_fill[s["category"]])
            link = ws3.cell(row=r, column=8)
            if x.get("url"):
                link.hyperlink = x["url"]
                link.font = Font(name="Microsoft YaHei", size=9, color="1D4ED8", underline="single")
            ws3.cell(row=r, column=6).alignment = Alignment(horizontal="center", vertical="top")
            ws3.row_dimensions[r].height = 50
            r += 1

    ws4 = wb.create_sheet("说明")
    ws4.sheet_view.showGridLines = False
    ws4.column_dimensions["A"].width = 110
    lines = [
        (f"全球要闻简报 · {data['date']} · 制表说明", Font(name="Microsoft YaHei", bold=True, size=16, color=ink)),
        ("", body),
        ("1. 时间口径：Asia/Shanghai 当日 08:00 前已刊发的 RSS 条目；回溯窗口 48 小时。", body),
        ("2. 聚类：标题词重叠 + 专有名词重叠 + 序列相似度；同一媒体在同一故事中只保留一条。", body),
        ("3. 数字直接取自各源标题/摘要，未做二次计算；冲突数字并列保留。", body),
        ("4. 倾向标签描述媒体整体编辑立场，参考 AllSides、Ad Fontes 等公开评级，不判定单篇真伪。", body),
        ("5. 官媒单列；专业/一手不放进左右轴。", body),
        ("6. 自动聚合的覆盖缺口是真实的：单一来源条目会在明细中体现。", body),
        ("", body),
        (f"来源构成：{mix_text(data)}", small),
        ("本表为自动生成的研究简报，不构成投资、法律或政治建议。", small),
    ]
    for i, (text, font) in enumerate(lines, 1):
        c = ws4.cell(row=i, column=1, value=text)
        c.font = font
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws4.row_dimensions[i].height = 28 if i == 1 else 20
    for sh in (ws, ws2, ws3):
        sh.page_setup.orientation = "landscape"
        sh.page_setup.fitToWidth = 1
        sh.sheet_properties.pageSetUpPr.fitToPage = True
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    wb.save(path)


def render_archive(docs_dir: str, css: str) -> str:
    files = sorted(
        [f for f in os.listdir(docs_dir) if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.html", f)],
        reverse=True,
    )
    cards = []
    for f in files:
        date = f[:-5]
        cards.append(
            f'<a class="card" href="{f}"><span class="card-date">{date}</span>'
            f'<span class="card-title">全球要闻简报</span><span class="card-arrow">→</span></a>'
        )
    body = "".join(cards) or '<p class="empty">还没有存档。</p>'
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>往期存档 · 全球要闻简报</title>
<style>{css}
.archive{{max-width:900px;margin:0 auto;padding:48px 24px}}
.card{{display:flex;gap:16px;align-items:baseline;padding:16px 4px;border-bottom:1px solid var(--line);text-decoration:none}}
.card:hover{{background:#fffdf6}}
.card-date{{font:700 12px ui-monospace,monospace;color:var(--red);width:110px}}
.card-title{{font-family:"Noto Serif SC",serif;font-size:18px}}
.card-arrow{{margin-left:auto;color:var(--muted)}}
.empty{{color:var(--muted)}}
</style></head><body><div class="archive">
<div class="kicker">ARCHIVE · 往期存档</div>
<h1 style="font-size:44px;margin:10px 0 20px">全球要闻简报</h1>
<p><a href="index.html">← 返回最新一期</a></p>
{body}</div></body></html>"""
