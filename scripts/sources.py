# -*- coding: utf-8 -*-
"""Source registry: RSS feeds, political-lean labels, and Google News fallbacks.

Edit this file to add or remove outlets. Keep the lean labels coarse and
transparent: they describe an outlet's overall editorial stance, not the truth
of any single article.
"""
from __future__ import annotations

from dataclasses import dataclass

LEANS = ["左", "中左", "中", "中右", "右", "官媒", "专业", "一手"]
LEAN_BUCKET = {
    "左": "left", "中左": "left",
    "中": "center",
    "中右": "right", "右": "right",
    "官媒": "state",
    "专业": "pro", "一手": "primary",
    "未评级": "other",
}
LEAN_DESC = {
    "左": "偏自由派/进步派",
    "中左": "轻微偏左",
    "中": "中间/通讯社",
    "中右": "轻微偏右",
    "右": "偏保守派",
    "官媒": "国家或政党直接控制",
    "专业": "体育/行业媒体",
    "一手": "公司或机构官方",
    "未评级": "未纳入评级",
}


@dataclass(frozen=True)
class Feed:
    key: str
    outlet: str
    lean: str
    category: str
    url: str


# Direct RSS feeds. A missing feed is logged and skipped; the build continues.
FEEDS: list[Feed] = [
    # ---------------- 政治 ----------------
    Feed("bbc-world", "BBC", "中", "政治", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    Feed("guardian-world", "The Guardian", "左", "政治", "https://www.theguardian.com/world/rss"),
    Feed("aljazeera-all", "Al Jazeera", "中左", "政治", "https://www.aljazeera.com/xml/rss/all.xml"),
    Feed("fox-politics", "Fox News", "右", "政治", "https://moxie.foxnews.com/google-publisher/politics.xml"),
    Feed("nypost", "New York Post", "右", "政治", "https://nypost.com/feed/"),
    Feed("npr-politics", "NPR", "中左", "政治", "https://feeds.npr.org/1014/rss.xml"),
    Feed("wsj-world", "The Wall Street Journal", "中右", "政治", "https://feeds.a.dj.com/rss/RSSWorldNews.xml"),
    Feed("jpost", "The Jerusalem Post", "中右", "政治", "https://www.jpost.com/rss/rssfeedsfrontpage.aspx"),
    Feed("arabnews", "Arab News", "中", "政治", "https://www.arabnews.com/rss.xml"),
    Feed("iranintl", "Iran International", "右", "政治", "https://www.iranintl.com/en/rss"),
    Feed("cna-world", "Channel NewsAsia", "中", "政治", "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml"),
    Feed("dw-world", "Deutsche Welle", "中", "政治", "https://rss.dw.com/rdf/rss-en-world"),
    Feed("france24", "France 24", "中", "政治", "https://www.france24.com/en/rss"),
    Feed("politico-eu", "Politico", "中", "政治", "https://www.politico.eu/feed/"),

    # ---------------- 经济 ----------------
    Feed("bbc-business", "BBC", "中", "经济", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    Feed("guardian-business", "The Guardian", "左", "经济", "https://www.theguardian.com/uk/business/rss"),
    Feed("cnbc-economy", "CNBC", "中", "经济", "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
    Feed("wsj-markets", "The Wall Street Journal", "中右", "经济", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    Feed("fox-business", "Fox Business", "右", "经济", "https://moxie.foxbusiness.com/google-publisher/markets.xml"),
    Feed("npr-business", "NPR", "中左", "经济", "https://feeds.npr.org/1006/rss.xml"),
    Feed("scmp-business", "South China Morning Post", "中", "经济", "https://www.scmp.com/rss/92/feed"),
    Feed("marketwatch", "MarketWatch", "中", "经济", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    Feed("economist-finance", "The Economist", "中右", "经济", "https://www.economist.com/finance-and-economics/rss.xml"),

    # ---------------- F1 ----------------
    Feed("bbc-f1", "BBC", "中", "F1", "https://feeds.bbci.co.uk/sport/formula1/rss.xml"),
    Feed("guardian-f1", "The Guardian", "左", "F1", "https://www.theguardian.com/sport/formulaone/rss"),
    Feed("sky-f1", "Sky Sports", "中", "F1", "https://www.skysports.com/rss/12433"),
    Feed("espn-f1", "ESPN", "中", "F1", "https://www.espn.com/espn/rss/f1/news"),
    Feed("motorsport-f1", "Motorsport.com", "专业", "F1", "https://www.motorsport.com/rss/f1/news/"),
    Feed("f1-official", "Formula1.com", "一手", "F1", "https://www.formula1.com/en/latest/all.xml"),
    Feed("dailymail-f1", "Daily Mail", "右", "F1", "https://www.dailymail.co.uk/sport/formulaone/index.rss"),
    Feed("express-f1", "Express", "右", "F1", "https://www.express.co.uk/posts/rss/24/formula-one"),

    Feed("therace-f1", "The Race", "专业", "F1", "https://www.the-race.com/rss/"),

    # ---------------- AI ----------------
    Feed("bbc-tech", "BBC", "中", "AI", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    Feed("guardian-ai", "The Guardian", "左", "AI", "https://www.theguardian.com/technology/artificialintelligenceai/rss"),
    Feed("techcrunch-ai", "TechCrunch", "中", "AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    Feed("verge-ai", "The Verge", "中左", "AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    Feed("ars-tech", "Ars Technica", "中", "AI", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    Feed("mittr", "MIT Technology Review", "中", "AI", "https://www.technologyreview.com/feed/"),
    Feed("cnbc-tech", "CNBC", "中", "AI", "https://www.cnbc.com/id/19854910/device/rss/rss.html"),
    Feed("fox-tech", "Fox News", "右", "AI", "https://moxie.foxnews.com/google-publisher/tech.xml"),
    Feed("wsj-tech", "The Wall Street Journal", "中右", "AI", "https://feeds.a.dj.com/rss/RSSWSJD.xml"),
    Feed("scmp-tech", "South China Morning Post", "中", "AI", "https://www.scmp.com/rss/36/feed"),
    Feed("venturebeat-ai", "VentureBeat", "中", "AI", "https://venturebeat.com/category/ai/feed/"),
    Feed("wired-ai", "Wired", "中左", "AI", "https://www.wired.com/feed/tag/ai/latest/rss"),
]

# Google News is used only when a category has too few direct-feed items.
GOOGLE_QUERIES: dict[str, list[str]] = {
    "政治": ["world politics", "US politics", "Iran war"],
    "经济": ["stock market", "Federal Reserve", "oil prices"],
    "F1": ["Formula 1", "Las Vegas Grand Prix"],
    "AI": ["artificial intelligence", "OpenAI", "AI regulation"],
}

# Conservative name-to-lean map for Google News results. Unknown outlets are
# labelled "未评级" rather than guessed.
OUTLET_LEAN_HINTS: list[tuple[str, str]] = [
    ("bbc", "中"), ("reuters", "中"), ("associated press", "中"), ("ap news", "中"),
    ("bloomberg", "中"), ("cnbc", "中"), ("financial times", "中"), ("nikkei", "中"),
    ("the wall street journal", "中右"), ("wall street journal", "中右"), ("barron", "中右"),
    ("the economist", "中右"), ("the telegraph", "中右"), ("times of london", "中右"),
    ("fox news", "右"), ("fox business", "右"), ("new york post", "右"),
    ("daily mail", "右"), ("the sun", "右"), ("washington examiner", "右"),
    ("the guardian", "左"), ("guardian", "左"), ("cnn", "左"), ("the new york times", "左"),
    ("new york times", "左"), ("msnbc", "左"), ("mother jones", "左"), ("vox", "左"),
    ("npr", "中左"), ("al jazeera", "中左"), ("the verge", "中左"), ("wired", "中左"),
    ("techcrunch", "中"), ("ars technica", "中"), ("mit technology review", "中"),
    ("south china morning post", "中"), ("scmp", "中"), ("sky sports", "中"),
    ("espn", "中"), ("motorsport", "专业"), ("autosport", "专业"), ("the race", "专业"),
    ("formula 1", "一手"), ("formula1", "一手"),
    ("xinhua", "官媒"), ("china daily", "官媒"), ("anadolu", "官媒"), ("antara", "官媒"),
    ("arab news", "中"), ("jerusalem post", "中右"), ("iran international", "右"),
]


def lean_of_outlet(name: str) -> str:
    key = (name or "").strip().lower()
    if not key:
        return "未评级"
    for hint, lean in OUTLET_LEAN_HINTS:
        if hint in key:
            return lean
    return "未评级"
