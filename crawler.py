# -*- coding: utf-8 -*-
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import ssl
import re

ssl._create_default_https_context = ssl._create_unverified_context

# 监控渠道：精心挑选的海外主要独立信源RSS
FEEDS = [
    {"name": "美国之音 (VOA)", "url": "https://www.voachinese.com/api/z$g_vte_kp", "source": "News"},
    {"name": "自由亚洲电台 (RFA)", "url": "https://www.rfa.org/mandarin/RSS", "source": "News"},
    {"name": "德国之声 (DW)", "url": "https://rss.dw.com/xml/rss-chi-all", "source": "News"}
]

# 主体监控对象
SUBJECTS = ["习近平", "Xi Jinping", "中南海", "领袖"]

# 🔴 自定义负面/高敏关键词列表（判定标准：主体词+负面词同时出现）
NEGATIVE_KEYWORDS = [
    "危机", "抗议", "打压", "倒退", "制裁", "独裁", "暴雷", "人权", "失业", "债务", 
    "爆雷", "独裁者", "言论控制", "极权", "反腐", "清洗", "扼杀", "专制", "严控", "逮捕", 
    "判刑", "打压", "冲突", "恶化", "受阻", "阻碍", "限制", "监禁", "审判", "丑闻"
]

def is_within_24_hours(pub_date_str):
    """验证文章是否在严格的 24 小时以内，并转换时区为北京时间"""
    if not pub_date_str:
        return False, ""
    try:
        # 将外媒RSS各种复杂的标准时间格式转换为Python可以计算的时间
        pub_datetime = parsedate_to_datetime(pub_date_str)
        if pub_datetime.tzinfo is None:
            pub_datetime = pub_datetime.replace(tzinfo=timezone.utc)
        
        # 获得当前的国际标准时间
        now = datetime.now(timezone.utc)
        diff = now - pub_datetime
        
        # 24 小时 = 86400 秒。允许 1 小时的系统时差冗余 (允许轻微偏差)
        if -3600 <= diff.total_seconds() <= 86400:
            # 统一自动转换输出为北京时间 (UTC+8)
            cst_tz = timezone(timedelta(hours=8))
            pub_datetime_cst = pub_datetime.astimezone(cst_tz)
            return True, pub_datetime_cst.strftime("%Y-%m-%d %H:%M")
        return False, ""
    except Exception as e:
        print(f"解析文章时间失败 {pub_date_str}: {e}")
        return False, ""

def fetch_feed(feed_info):
    articles = []
    try:
        req = urllib.request.Request(
            feed_info["url"], 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            xml_data = response.read()
        
        root = ET.fromstring(xml_data)
        for item in root.findall('.//item'):
            title = item.find('title').text if item.find('title') is not None else ""
            link = item.find('link').text if item.find('link') is not None else ""
            desc = item.find('description').text if item.find('description') is not None else ""
            pub_date_el = item.find('pubDate')
            pub_date_str = pub_date_el.text if pub_date_el is not None else ""
            
            # 1. 精准的时间差截断验证
            in_range, formatted_time = is_within_24_hours(pub_date_str)
            if not in_range:
                continue # 超出 24 小时，直接丢弃，不予处理
            
            full_text = (title + " " + desc).lower()
            
            # 2. 判定逻辑： 必须包含主体监控对象，且必须包含至少一个负面词
            has_subject = any(sub.lower() in full_text for sub in SUBJECTS)
            matched_negatives = [neg for neg in NEGATIVE_KEYWORDS if neg in full_text]
            
            if has_subject and len(matched_negatives) > 0:
                articles.append({
                    "title": title.strip(),
                    "source": feed_info["source"],
                    "sourceName": feed_info["name"],
                    "time": formatted_time,
                    "url": link,
                    "sentiment": "High" if len(matched_negatives) > 2 else "Medium",
                    "summary": re.sub('<[^<]+?>', '', desc)[:120] + "...",
                    "keywords": list(set(matched_negatives))
                })
    except Exception as e:
        print(f"Error reading {feed_info['name']}: {e}")
    return articles

if __name__ == "__main__":
    all_data = []
    for f in FEEDS:
        all_data.extend(fetch_feed(f))
    
    # 过滤重复新闻
    seen = set()
    unique_data = []
    for item in all_data:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique_data.append(item)
            
    # 按照时间从新到旧重新排序
    unique_data.sort(key=lambda x: x["time"], reverse=True)

    # 写入 JSON。如果没有数据，写入干净的空列表 []，网页前端将自适应展示安全提示
    with open('opinion_data.json', 'w', encoding='utf-8') as f:
        json.dump(unique_data, f, ensure_ascii=False, indent=4)
    print(f"数据处理完毕。共成功保留 {len(unique_data)} 条24小时内的时效性信息。")
