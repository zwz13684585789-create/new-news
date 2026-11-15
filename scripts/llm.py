# -*- coding: utf-8 -*-
"""Optional Chinese rewriting through an OpenAI-compatible chat endpoint.

Priority:
1. LLM_BASE_URL + LLM_API_KEY + LLM_MODEL (any compatible endpoint)
2. DEEPSEEK_API_KEY (api.deepseek.com)
3. GITHUB_TOKEN (GitHub Models, models.github.ai)

Without any of these the build still works; headlines and summaries stay in
their original English and the page shows a notice.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request

SYSTEM = "你是一名严谨的国际新闻编辑，擅长把英文通讯社与报纸的标题改写成中文简报。你只使用用户提供的事实，绝不补充新数字、新引语或新结论。"

PROMPT = """请根据下面的英文 RSS 条目，写一份中文简报。只输出 JSON，不要 Markdown 代码块。

硬性要求：
1. 只能使用输入里的事实。输入没有的数字、引语、因果判断，一律不要写；信息不足就写“细节有限”。
2. 每条故事：
   - title：18—34 个汉字，具体、克制，不用“震惊/炸裂”一类词。
   - facts：3 条，每条 30—70 字，按重要性排序；保留关键数字与动作。
   - framing：20—60 字，说明不同来源的叙事差异；如果来源角度接近，就直说“角度接近”。
   - angles：给输入中的每一家来源写一句 12—30 字的“报道角度”，只描述该条标题/摘要的措辞重点，不要编造其立场。
3. lede：80—120 字，概括今天四条线（政治/经济/F1/AI）的共同点，不要复述标题。
4. takeaways：3 条，每条 30—50 字，是判断而不是事实复述。
5. 如果某条故事只有一家来源，framing 要注明“单一来源”。

JSON 结构：
{
  "lede": "……",
  "takeaways": ["……", "……", "……"],
  "stories": {
    "P1": {
      "title": "……",
      "facts": ["……", "……", "……"],
      "framing": "……",
      "angles": {"BBC": "……", "CNN": "……"}
    }
  }
}

输入：
{payload}
"""


def _provider() -> tuple[str, str, str, str]:
    """Return (name, base_url, api_key, model)."""
    if os.getenv("LLM_BASE_URL") and os.getenv("LLM_API_KEY"):
        return ("custom", os.environ["LLM_BASE_URL"].rstrip("/"),
                os.environ["LLM_API_KEY"], os.getenv("LLM_MODEL", "gpt-4o-mini"))
    if os.getenv("DEEPSEEK_API_KEY"):
        return ("deepseek", "https://api.deepseek.com",
                os.environ["DEEPSEEK_API_KEY"], os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))
    if os.getenv("GITHUB_TOKEN"):
        return ("github", "https://models.github.ai/inference",
                os.environ["GITHUB_TOKEN"], os.getenv("GITHUB_MODEL", "openai/gpt-4o-mini"))
    return ("", "", "", "")


def _payload(data: dict) -> str:
    rows = []
    for story in data.get("stories", []):
        items = story.get("items", [])
        src_rows = []
        for idx, src in enumerate(story.get("sources", [])):
            summary = items[idx].get("summary", "") if idx < len(items) else ""
            title = items[idx].get("title", "") if idx < len(items) else ""
            src_rows.append({
                "outlet": src["name"],
                "lean": src["lean"],
                "title": title,
                "summary": (summary or "")[:260],
            })
        rows.append({"id": story["id"], "category": story["category"], "items": src_rows})
    return json.dumps(rows, ensure_ascii=False, indent=1)


def _call(base_url: str, api_key: str, model: str, payload: str, name: str) -> str:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": PROMPT.replace("{payload}", payload)},
        ],
        "temperature": 0.25,
        "max_tokens": 5000,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if name == "github":
        headers.update({"Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28"})
    req = urllib.request.Request(
        base_url + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read().decode("utf-8", "ignore")
    parsed = json.loads(raw)
    return parsed["choices"][0]["message"]["content"]


def _extract_json(text: str) -> dict:
    text = text.strip()
    fence = chr(96) * 3
    if text.startswith(fence):
        text = re.sub(r"^" + fence + r"(?:json)?\s*", "", text)
        text = re.sub(r"\s*" + fence + r"$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in response")
    return json.loads(text[start:end + 1])


def summarize(data: dict) -> dict:
    name, base_url, api_key, model = _provider()
    if not name:
        data["llm_error"] = "未配置模型 API"
        return data

    payload = _payload(data)
    last_error = ""
    for attempt in range(2):
        try:
            content = _call(base_url, api_key, model, payload, name)
            parsed = _extract_json(content)
            stories = parsed.get("stories") or {}
            applied = 0
            for story in data.get("stories", []):
                got = stories.get(story["id"])
                if not isinstance(got, dict):
                    continue
                title = got.get("title")
                facts = got.get("facts")
                framing = got.get("framing")
                angles = got.get("angles") if isinstance(got.get("angles"), dict) else {}
                if isinstance(title, str) and 6 <= len(title.strip()) <= 80:
                    story["title"] = title.strip()
                if isinstance(facts, list) and facts:
                    clean = [str(x).strip() for x in facts if str(x).strip()][:5]
                    if clean:
                        story["facts"] = clean
                if isinstance(framing, str) and framing.strip():
                    story["framing"] = framing.strip()
                for src in story.get("sources", []):
                    angle = angles.get(src["name"]) or angles.get(src["name"].split("（")[0])
                    if isinstance(angle, str) and angle.strip():
                        src["angle"] = angle.strip()
                applied += 1
            if applied == 0:
                raise ValueError("model returned no usable stories")
            lede = parsed.get("lede")
            takes = parsed.get("takeaways")
            if isinstance(lede, str) and lede.strip():
                data["lede"] = lede.strip()
            if isinstance(takes, list) and takes:
                data["takeaways"] = [str(x).strip() for x in takes if str(x).strip()][:4]
            data["llm_used"] = True
            data["llm_provider"] = name
            data.pop("llm_error", None)
            return data
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {str(exc)[:240]}"
            if attempt == 0:
                time.sleep(2)
    data["llm_error"] = last_error
    return data
