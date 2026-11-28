# -*- coding: utf-8 -*-
"""Curate one dated briefing by replacing weak auto-selected stories.

Loads the generated dataset for the date, swaps in manually verified stories,
then renders HTML/Markdown/XLSX with the normal renderer.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import render  # noqa: E402


def src(name, lean, angle, url):
    return {"name": name, "lean": lean, "angle": angle, "url": url}


def item(outlet, lean, title, summary, url):
    return {"outlet": outlet, "lean": lean, "title": title, "summary": summary, "url": url}


def story(sid, category, title, facts, sources, framing, items):
    return {
        "id": sid,
        "category": category,
        "title": title,
        "facts": facts,
        "sources": sources,
        "framing": framing,
        "items": items,
    }


def main() -> int:
    date_str = sys.argv[1] if len(sys.argv) > 1 else "2026-11-28"
    base = ROOT / "build" / date_str / "data" / f"{date_str}.json"
    data = json.loads(base.read_text(encoding="utf-8"))
    old = {s["id"]: s for s in data["stories"]}

    # P3: replace the misattributed Guardian live-blog URL with a real Spain article.
    p3 = old["P3"]
    p3["facts"][1] = "卫报称西班牙受气候危机冲击严重，但选前辩论对气候议题着墨很少，右翼联盟可能逆转现有环保政策。"
    for s in p3["sources"]:
        if s["name"] == "The Guardian":
            s["url"] = "https://www.theguardian.com/world/2026/nov/25/spain-election-climate-crisis"
            s["angle"] = "追问气候危机为何在选前被淡化，关注右翼联盟可能逆转环保政策。"
    p3["framing"] = ("三家来源均围绕选前最后阶段：BBC 与法国24 聚焦桑切斯与右翼对手的攻防、"
                     "选民动员；卫报从气候议题切入，指出该议题在选前被明显淡化。")

    # E1: add a right-leaning angle without using it as a hard fact.
    e1 = old["E1"]
    e1["sources"].append(src(
        "Fox Business (via Yahoo Finance)", "右",
        "以“特朗普对市场影响力减弱”为框架评论黄仁勋复职与英伟达大涨。",
        "https://finance.yahoo.com/markets/stocks/articles/fox-host-reveals-sign-trump-234652391.html",
    ))
    e1["framing"] = ("四家来源角度互补：南华早报以数字盘点市场波动，CNBC 聚焦中国工厂利润与 AI 分化，"
                     "BBC 聚焦美国新关税范围，福克斯商业则从特朗普政治影响力角度评论英伟达大涨；"
                     "前三家均未给出关税具体税率细节。")

    # F1: drop a BBC claim that is not in the selected source set.
    f1 = old["F1"]
    f1["facts"] = [x for x in f1["facts"] if not x.startswith("BBC称")]

    replacements = {}
    replacements["P2"] = story(
        "P2", "政治",
        "乌克兰提出黑海停火方案，等待俄方回应",
        [
            "乌克兰外长瑟比加称，乌方已向国际伙伴提交黑海停火“实际方案”，目标是恢复航行自由与粮食出口，目前等待俄方回应。",
            "方案公布前一天，俄罗斯攻击了两艘外国粮船；乌方称黑海已重新成为战场，粮食出口较上一季明显下降。",
            "泽连斯基批评特朗普与普京的“友谊”未带来停火；普京则主持新核潜艇入列，显示俄方仍在强化海上力量。",
        ],
        [
            src("France 24", "中", "报道乌方提交方案、等待莫斯科回应，并提及此前粮船遇袭。",
                "https://www.france24.com/en/europe/20261127-ukraine-submits-black-sea-ceasefire-offer-awaits-russian-response"),
            src("Al Jazeera", "中左", "聚焦黑海粮食出口与泽连斯基对特朗普-普京关系的批评。",
                "https://www.aljazeera.com/news/2026/11/27/kyiv-offers-black-sea-ceasefire-as-putin-expands-russias-navy"),
        ],
        "两家来源均确认乌方已提交方案且俄方未回应；法国24 侧重方案内容与粮船遇袭，半岛电视台侧重泽连斯基的外交批评与俄海军动作。",
        [
            item("France 24", "中", "Ukraine submits Black Sea ceasefire offer, awaits Russian response",
                 "Kyiv has handed partners practical proposals for a Black Sea ceasefire meant to restore navigation and food exports; Moscow has not replied.",
                 "https://www.france24.com/en/europe/20261127-ukraine-submits-black-sea-ceasefire-offer-awaits-russian-response"),
            item("Al Jazeera", "中左", "Kyiv offers Black Sea ceasefire as Putin expands Russia's navy",
                 "Ukraine wants a ceasefire to protect grain exports; Zelensky criticises Trump's friendship with Putin as Russia adds a new submarine.",
                 "https://www.aljazeera.com/news/2026/11/27/kyiv-offers-black-sea-ceasefire-as-putin-expands-russias-navy"),
        ],
    )

    replacements["E4"] = story(
        "E4", "经济",
        "Norse Atlantic 停飞：伊朗战争推高燃油成本，跨大西洋廉航走向破产",
        [
            "Norse Atlantic 暂停全部航班；BBC 称公司正寻求紧急融资，若无救助将申请破产。",
            "卫报称公司已申请破产并取消所有未来航班，直接原因是伊朗战争推高航空燃油成本；公司要求旅客不要前往机场。",
            "德国之声称这家成立仅数年的廉航长期难以盈利，燃油价格飙升成为最后一击。",
        ],
        [
            src("The Guardian", "左", "称公司已申请破产、取消未来航班，归因于战争推高燃油成本。",
                "https://www.theguardian.com/business/2026/nov/27/norse-atlantic-airways-files-for-bankruptcy-cancels-all-future-flights"),
            src("Deutsche Welle", "中", "梳理公司短历史与盈利困境，强调燃油冲击是最后一击。",
                "https://www.dw.com/en/airline-norse-atlantic-files-for-bankruptcy-succumbing-to-aviation-fuel-costs/a-80076728"),
            src("BBC", "中", "称公司暂停航班、寻求紧急融资，未排除破产。",
                "https://www.bbc.co.uk/news/articles/c9kgmd0ldy0lo"),
        ],
        "三家来源对“已申请破产”还是“若无救助将申请破产”表述不一：卫报用已完成时，BBC 仍称寻求融资；可交叉确认的核心事实是停飞与燃油成本冲击。",
        [
            item("The Guardian", "左", "Norse Atlantic Airways files for bankruptcy and cancels all future flights",
                 "The budget transatlantic airline has filed for bankruptcy, cancelled all future flights and told customers not to travel to airports.",
                 "https://www.theguardian.com/business/2026/nov/27/norse-atlantic-airways-files-for-bankruptcy-cancels-all-future-flights"),
            item("Deutsche Welle", "中", "Airline Norse Atlantic files for bankruptcy, succumbing to aviation fuel costs",
                 "The young airline had struggled to turn a profit; the fuel-price spike caused by the Iran war delivered the final blow.",
                 "https://www.dw.com/en/airline-norse-atlantic-files-for-bankruptcy-succumbing-to-aviation-fuel-costs/a-80076728"),
            item("BBC", "中", "Norse Atlantic suspends all flights and seeks urgent funding",
                 "The airline has suspended flights and is seeking a lifeline; without it, it will file for bankruptcy.",
                 "https://www.bbc.co.uk/news/articles/c9kgmd0ldy0lo"),
        ],
    )

    replacements["F2"] = story(
        "F2", "F1",
        "法拉利内耗公开化：瓦塞尔称勒克莱尔与汉密尔顿“难以管理”",
        [
            "法拉利领队瓦塞尔承认勒克莱尔与汉密尔顿的关系“已难以管理”，并暗示后悔让两人成为队友。",
            "两人本赛季多次在赛道上碰撞；勒克莱尔否认合同中有“一号车手条款”，称赛后已与汉密尔顿进行良好沟通。",
            "汉密尔顿称法拉利正处于“非常非常困难的时期”；卫报称车队在卡塔尔站前进行了紧急会谈。",
        ],
        [
            src("The Guardian", "左", "报道两人代价高昂的赛道冲突与卡塔尔站前的紧张气氛。",
                "https://www.theguardian.com/sport/2026/nov/27/ferrari-lewis-hamilton-charles-leclerc-qatar-grand-prix-f1"),
            src("ESPN", "中", "引瓦塞尔称局面“难以管理”，暗示后悔让两人搭档。",
                "https://www.espn.com/f1/story/_/id/50472137/f1-ferrari-charles-leclerc-lewis-hamilton-las-vegas-grand-prix-formula-1"),
            src("Sky Sports", "中", "报道勒克莱尔否认“一号车手条款”，称碰撞后沟通良好。",
                "https://www.skysports.com/f1/news/12433/13616753/charles-leclerc-denies-presence-of-no-1-driver-clause-in-ferrari-contract-as-he-and-lewis-hamilton-hold-good-discussions-after-collision"),
            src("BBC", "中", "引汉密尔顿称法拉利处于“非常非常困难的时期”。",
                "https://www.bbc.co.uk/sport/formula1/articles/c6j9mw2dkzrxo"),
        ],
        "四家来源均确认车队内部紧张；ESPN 与 BBC 引瓦塞尔、汉密尔顿的强硬表述，天空体育与卫报补充勒克莱尔的降温表态，角度从“危机”到“试图修复”不等。",
        [
            item("The Guardian", "左", "Ferrari's Lewis Hamilton and Charles Leclerc tensions boil over before Qatar GP",
                 "Costly on-track clashes have left Ferrari managing a fragile relationship between its two drivers.",
                 "https://www.theguardian.com/sport/2026/nov/27/ferrari-lewis-hamilton-charles-leclerc-qatar-grand-prix-f1"),
            item("ESPN", "中", "Vasseur admits Ferrari driver situation 'unmanageable'",
                 "Ferrari team principal Fred Vasseur admitted the Leclerc-Hamilton pairing has been difficult to manage and hinted at regret.",
                 "https://www.espn.com/f1/story/_/id/50472137/f1-ferrari-charles-leclerc-lewis-hamilton-las-vegas-grand-prix-formula-1"),
            item("Sky Sports", "中", "Leclerc denies No.1 driver clause after collision with Hamilton",
                 "Leclerc said there is no number-one clause in his contract and that the pair had good discussions after their latest collision.",
                 "https://www.skysports.com/f1/news/12433/13616753/charles-leclerc-denies-presence-of-no-1-driver-clause-in-ferrari-contract-as-he-and-lewis-hamilton-hold-good-discussions-after-collision"),
            item("BBC", "中", "Hamilton: Ferrari in 'very, very challenging times'",
                 "Lewis Hamilton described Ferrari's season as a very difficult period after another troubled weekend.",
                 "https://www.bbc.co.uk/sport/formula1/articles/c6j9mw2dkzrxo"),
        ],
    )

    replacements["F3"] = story(
        "F3", "F1",
        "奥迪上诉被驳回：意大利站角田裕毅争议落幕",
        [
            "国际上诉法院驳回奥迪对意大利大奖赛“起步中止”事件中角田裕毅处罚的上诉，蒙扎站结果在事发两个多月后正式确认。",
            "奥迪认为角田在重新起步时不应免于处罚；Motorsport.com 称听证会于 11 月 25 日举行。",
            "F1.com 称裁决维持原判，奥迪的申诉未能改变比赛分类。",
        ],
        [
            src("Formula1.com", "一手", "提供裁决结果与国际上诉法院听证程序。",
                "https://www.formula1.com/en/latest/article/audis-italian-grand-prix-appeal-over-tsunoda-restart-decision-is-dismissed.53YK6RxY4GWQ0WvgCUm3xh"),
            src("Motorsport.com", "专业", "解释奥迪的处罚主张与听证时间。",
                "https://www.motorsport.com/f1/news/audi-appeal-against-yuki-tsunoda-dismissed-heres-why/10878357/"),
        ],
        "两家来源结论一致；F1.com 提供裁决与程序，Motorsport.com 解释奥迪为何认为角田应受罚。",
        [
            item("Formula1.com", "一手", "Audi's Italian Grand Prix appeal over Tsunoda restart decision is dismissed",
                 "The International Court of Appeal dismissed Audi's appeal; the Monza result stands.",
                 "https://www.formula1.com/en/latest/article/audis-italian-grand-prix-appeal-over-tsunoda-restart-decision-is-dismissed.53YK6RxY4GWQ0WvgCUm3xh"),
            item("Motorsport.com", "专业", "Audi appeal against Yuki Tsunoda dismissed - here's why",
                 "Audi believed Tsunoda deserved a time penalty for the aborted start; the hearing was held on November 25.",
                 "https://www.motorsport.com/f1/news/audi-appeal-against-yuki-tsunoda-dismissed-heres-why/10878357/"),
        ],
    )

    replacements["F4"] = story(
        "F4", "F1",
        "贝尔曼与哈斯续约一年，2027 F1 车手阵容确定",
        [
            "哈斯车队宣布与贝尔曼续约一年，英国人将在 2027 赛季继续效力。",
            "贝尔曼将搭档巴西新秀拉斐尔·卡马拉；Motorsport.com 称 2027 车手阵容由此全部确定。",
            "天空体育称谈判持续较久，最终在卡塔尔站前敲定。",
        ],
        [
            src("BBC", "中", "确认贝尔曼 2027 年继续效力哈斯。",
                "https://www.bbc.co.uk/sport/formula1/articles/cqx2wxyk7343o"),
            src("Motorsport.com", "专业", "称一年合约已定，2027 全部车手席位确定。",
                "https://www.motorsport.com/f1/news/oliver-bearman-locks-in-haas-f1-seat-as-2027-grid-officially-set/10877802/"),
            src("Sky Sports", "中", "称谈判持续较久，卡塔尔站前最终敲定。",
                "https://www.skysports.com/f1/news/12433/13610208/oliver-bearman-to-remain-with-haas-for-2027-f1-season-after-new-contract-finally-agreed-ahead-of-qatar-gp"),
        ],
        "三家来源均确认续约；BBC 与天空体育侧重谈判过程，Motorsport.com 侧重 2027 阵容全局。",
        [
            item("BBC", "中", "Bearman continues with Haas in 2027",
                 "Oliver Bearman will remain with Haas for the 2027 season.",
                 "https://www.bbc.co.uk/sport/formula1/articles/cqx2wxyk7343o"),
            item("Motorsport.com", "专业", "Oliver Bearman locks in Haas F1 seat as 2027 grid officially set",
                 "Bearman signed a one-year deal and will partner Brazilian rookie Rafael Camara; the 2027 grid is complete.",
                 "https://www.motorsport.com/f1/news/oliver-bearman-locks-in-haas-f1-seat-as-2027-grid-officially-set/10877802/"),
            item("Sky Sports", "中", "Bearman to remain with Haas for 2027 after new contract agreed",
                 "The one-year extension was finally agreed ahead of the Qatar Grand Prix after protracted talks.",
                 "https://www.skysports.com/f1/news/12433/13610208/oliver-bearman-to-remain-with-haas-for-2027-f1-season-after-new-contract-finally-agreed-ahead-of-qatar-gp"),
        ],
    )

    replacements["A2"] = story(
        "A2", "AI",
        "黄仁勋将赴国会作证：对华出口管制、复职争议与赦免言论交织",
        [
            "黄仁勋将于 12 月 3 日出席参议院银行委员会公开听证，主题为“保护美国 AI 优势：出口管制监督”；12 月 1 日起先接受众议院三个委员会闭门问询。",
            "参议院民主党领袖舒默指控黄仁勋“向中国运送极先进芯片、违反出口管制”，并将其比作冷战时期向苏联出售火箭发动机。",
            "特朗普表示若有必要会考虑赦免黄仁勋；MSNBC 称这使听证会同时成为对总统干预企业治理的检验。",
            "英伟达股价在黄仁勋复职当日大涨 31%，市值增加约 9500 亿美元。",
        ],
        [
            src("CP24 / AP", "中", "报道舒默的违法指控与黄仁勋国会作证安排。",
                "https://www.cp24.com/news/world/2026/11/24/democratic-senate-leader-accuses-nvidia-ceo-of-violating-us-export-control-law/"),
            src("MSNBC", "左", "聚焦特朗普赦免言论与总统干预企业治理的争议。",
                "https://www.ms.now/rachel-maddow-show/maddowblog/trump-jensen-huang-nvidia-pardon-congress-testimony-fifth-amendment"),
            src("Engadget", "中", "确认 12 月 3 日公开听证与 12 月 1 日闭门问询日程。",
                "https://www.engadget.com/2325655/nvidia-jensen-huang-will-testify-publlicly-before-senators-on-december-3/"),
        ],
        "AP 与 Engadget 确认听证日程与指控，MSNBC 补充特朗普赦免言论；三家均未证实芯片流向的实质指控，听证会将成为关键节点。",
        [
            item("CP24 / AP", "中", "Democratic Senate leader accuses Nvidia CEO of violating U.S. export control law",
                 "Chuck Schumer accused Jensen Huang of violating export-control law, comparing the alleged chip shipments to selling rocket engines to the Soviets.",
                 "https://www.cp24.com/news/world/2026/11/24/democratic-senate-leader-accuses-nvidia-ceo-of-violating-us-export-control-law/"),
            item("MSNBC", "左", "Trump opens the door to a pardon for Nvidia's Huang ahead of congressional testimony",
                 "Huang is scheduled to testify publicly before the Senate Banking Committee on December 3 after closed-door House interviews.",
                 "https://www.ms.now/rachel-maddow-show/maddowblog/trump-jensen-huang-nvidia-pardon-congress-testimony-fifth-amendment"),
            item("Engadget", "中", "NVIDIA's Jensen Huang will testify publicly before senators on December 3",
                 "The Senate Banking Committee hearing will focus on export-control oversight; House panels interview Huang on December 1.",
                 "https://www.engadget.com/2325655/nvidia-jensen-huang-will-testify-publlicly-before-senators-on-december-3/"),
        ],
    )

    replacements["A3"] = story(
        "A3", "AI",
        "AI 购物助手遭遇平台封堵：代理电商的开放性与责任之争",
        [
            "OpenAI、Meta、Google 等推出的 AI 购物助手在假日季快速普及，可代用户比价、找礼物。",
            "亚马逊等零售商开始限制第三方 AI 代理抓取商品与下单，CNBC 称这可能抑制代理电商的增长。",
            "卫报称零售商对 AI 助手出错时的责任归属没有答案；Meta Muse 等工具正在改变平台与商家的流量分配。",
        ],
        [
            src("CNBC", "中", "聚焦亚马逊等平台对第三方 AI 购物代理的封堵。",
                "https://www.cnbc.com/2026/11/27/ai-shopping-agents-retailer-blocks.html"),
            src("The Guardian", "左", "聚焦 AI 助手出错时的责任归属与商家风险。",
                "https://www.theguardian.com/business/2026/nov/27/retailers-ai-shopping-assistants-black-friday-brands-meta-muse"),
        ],
        "CNBC 聚焦平台封锁与商业摩擦，卫报聚焦责任与商家风险；两家均认为 AI 代理会改变电商入口，但监管与责任规则尚未跟上。",
        [
            item("CNBC", "中", "AI shopping agents are having a moment, but Amazon and other sites threaten to stunt their growth",
                 "Agents from OpenAI, Meta, Google and Instinct promise to help users shop, but they are hitting roadblocks at Amazon and other retailers.",
                 "https://www.cnbc.com/2026/11/27/ai-shopping-agents-retailer-blocks.html"),
            item("The Guardian", "左", "'If the bot gets it wrong, who's liable?' Retailers enter the unknown with AI shopping assistants",
                 "Retailers are adopting tools such as Meta Muse but are unsure who bears responsibility when an agent makes a mistake.",
                 "https://www.theguardian.com/business/2026/nov/27/retailers-ai-shopping-assistants-black-friday-brands-meta-muse"),
        ],
    )

    replacements["A4"] = story(
        "A4", "AI",
        "SAP 拟裁至少 1 万人：AI 重组波及 9% 全球员工",
        [
            "SAP 正考虑在 AI 驱动的重组中裁减至少 1 万个岗位，约占其 11 万全球员工的 9%。",
            "彭博社首先报道该计划；路透社称无法独立核实，SAP 未立即置评，劳资委员会尚未听取简报。",
            "路透社称德国员工就业保障承诺延续至 2028 年，最终裁员规模仍可能在劳资谈判后变化。",
        ],
        [
            src("CNBC", "中", "报道 SAP 考虑至少 1 万个 AI 重组岗位削减。",
                "https://www.cnbc.com/2026/11/27/sap-job-cuts-ai-restructuring.html"),
            src("Reuters", "中", "强调消息来自彭博社、路透社无法独立核实，并补充劳资与就业保障背景。",
                "https://www.thestar.com.my/tech/tech-news/2026/11/27/sap-considers-at-least-10000-job-cuts-in-ai-restructuring-bloomberg-reports"),
        ],
        "两家来源均基于彭博社消息，CNBC 与路透社都未能独立证实；事实核心是“考虑中”的重组，不是已宣布的裁员。",
        [
            item("CNBC", "中", "SAP considering at least 10,000 job cuts in AI restructuring",
                 "SAP is considering cutting at least 10,000 jobs, about 9% of its 110,000-strong workforce, as part of an AI-driven restructuring.",
                 "https://www.cnbc.com/2026/11/27/sap-job-cuts-ai-restructuring.html"),
            item("Reuters", "中", "SAP considers at least 10,000 job cuts in AI restructuring, Bloomberg reports",
                 "Bloomberg reported the plan; Reuters could not independently verify it. The works council has not been briefed and Germany's employment guarantee runs through 2028.",
                 "https://www.thestar.com.my/tech/tech-news/2026/11/27/sap-considers-at-least-10000-job-cuts-in-ai-restructuring-bloomberg-reports"),
        ],
    )

    order = ["P1", "P2", "P3", "P4", "E1", "E2", "E3", "E4",
             "F1", "F2", "F3", "F4", "A1", "A2", "A3", "A4"]
    merged = []
    for sid in order:
        merged.append(replacements.get(sid, old[sid]))
    data["stories"] = merged

    # Fix the MarketWatch placeholder link in E2.
    for s in data["stories"]:
        if s["id"] == "E2":
            for x in s["sources"] + s.get("items", []):
                if x.get("url") == "WP-MKTW-0005371805":
                    x["url"] = "https://www.marketwatch.com/story/the-return-of-jensen-huang-has-saved-the-u-s-stock-market-for-now-why-the-rebound-may-not-last-f72656ce"

    data["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data["lede"] = (
        "今天的主线是“战争与规则的成本开始显性化”：黑海粮食通道与伊朗战事继续外溢，"
        "Norse Atlantic 成为燃油冲击下第一家倒下的跨大西洋廉航；AI 板块则在英伟达大涨、"
        "黄仁勋国会作证与 SAP 万人重组之间，同时接受市场、监管与就业三重检验。"
    )
    data["takeaways"] = [
        "政治：乌克兰把黑海停火与粮食出口绑定，俄方未回应；伊朗战事的无人机溯源、海上封锁与人权后果同时发酵。",
        "经济：英伟达一日大涨 31% 与 20–40% 新关税并行，Norse Atlantic 破产显示战争成本正传导到航空业。",
        "AI：黄仁勋 12 月 3 日国会作证、SAP 拟裁 1 万人、AI 购物代理遭平台封堵——治理与就业开始追赶估值。",
        "F1：卡塔尔站梅赛德斯周五统治，但轮胎 15 圈 100% 磨损与法拉利内耗是更大的变量。",
    ]
    data.setdefault("stats", {})["curated"] = True
    data["stats"]["stories"] = len(data["stories"])
    data["stats"]["sources"] = len(render.all_sources(data))

    out_dir = ROOT / "build" / f"{date_str}-curated"
    out_dir.mkdir(parents=True, exist_ok=True)
    css = (ROOT / "templates" / "style.css").read_text(encoding="utf-8")
    html = render.render_html(data, css)
    md = render.render_markdown(data)
    (out_dir / f"{date_str}.html").write_text(html, encoding="utf-8")
    (out_dir / f"{date_str}.md").write_text(md, encoding="utf-8")
    render.write_xlsx(data, str(out_dir / f"{date_str}.xlsx"))
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / "archive.html").write_text(render.render_archive(str(out_dir), css), encoding="utf-8")
    data_dir = out_dir / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / f"{date_str}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "date": date_str,
        "stories": len(data["stories"]),
        "sources": len(render.all_sources(data)),
        "html": str(out_dir / f"{date_str}.html"),
        "xlsx": str(out_dir / f"{date_str}.xlsx"),
        "mix": render.mix_text(data),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
