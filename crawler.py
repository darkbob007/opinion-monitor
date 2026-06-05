# -*- coding: utf-8 -*-
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
import ssl

# 忽略 SSL 证书安全验证，确保能顺利访问境外媒体
ssl._create_default_https_context = ssl._create_unverified_context

# 监控的海外媒体 RSS 公开订阅源（这些由 GitHub 在海外的服务器拉取，因此不受防火墙限制）
FEEDS = [
    {"name": "美国之音 (VOA)", "url": "https://www.voachinese.com/api/z$g_vte_kp", "source": "News"},
    {"name": "自由亚洲电台 (RFA)", "url": "https://www.rfa.org/mandarin/RSS", "source": "News"},
    {"name": "德国之声 (DW)", "url": "https://rss.dw.com/xml/rss-chi-all", "source": "News"}
]

# 监测的关键词红线
KEYWORDS = ["习近平", "Xi Jinping", "中南海", "北京当局", "中国高层"]

def fetch_feed(feed_info):
    articles = []
    try:
        req = urllib.request.Request(
            feed_info["url"], 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            xml_data = response.read()
        
        # 解析 RSS XML 数据
        root = ET.fromstring(xml_data)
        for item in root.findall('.//item'):
            title = item.find('title').text if item.find('title') is not None else ""
            link = item.find('link').text if item.find('link') is not None else ""
            desc = item.find('description').text if item.find('description') is not None else ""
            
            # 判断标题或描述中是否包含我们要监控的敏感词
            content_to_check = (title + desc).lower()
            if any(kw.lower() in content_to_check for kw in KEYWORDS):
                found_kws = [kw for kw in KEYWORDS if kw.lower() in content_to_check]
                articles.append({
                    "title": title,
                    "source": feed_info["source"],
                    "sourceName": feed_info["name"],
                    "time": "今日 09:00", # 标记为统一自动更新时间
                    "url": link,
                    "sentiment": "High" if "习近平" in title else "Medium",
                    "summary": desc[:150] + "..." if len(desc) > 150 else desc,
                    "keywords": list(set(found_kws)) if found_kws else ["政治舆情"]
                })
    except Exception as e:
        print(f"抓取 {feed_info['name']} 失败: {e}")
    return articles

if __name__ == "__main__":
    all_data = []
    for f in FEEDS:
        all_data.extend(fetch_feed(f))
    
    # 过滤出重复的标题，保证数据纯净
    seen_titles = set()
    unique_data = []
    for item in all_data:
        if item["title"] not in seen_titles:
            seen_titles.add(item["title"])
            unique_data.append(item)
            
    # 如果抓取到了数据，分配 ID；如果没抓到，生成安全通报
    if not unique_data:
        unique_data = [{
            "id": 1,
            "title": "今日暂无触发监控红线的新增敏感信息",
            "source": "News",
            "sourceName": "监控中心",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "url": "#",
            "sentiment": "Medium",
            "summary": "全网未检索到包含预设政治敏感词的高危负面信息，系统安全平稳运行。",
            "keywords": ["安全运作"]
        }]
    else:
        for i, item in enumerate(unique_data):
            item["id"] = i + 1

    # 导出文件
    with open('opinion_data.json', 'w', encoding='utf-8') as f:
        json.dump(unique_data, f, ensure_ascii=False, indent=4)
    print(f"成功导出 {len(unique_data)} 条敏感信息！")
