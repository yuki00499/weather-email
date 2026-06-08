# -*- coding: utf-8 -*-
"""天气数据获取模块 - 从 wttr.in 获取天气 JSON"""

import logging
import requests

log = logging.getLogger(__name__)

# ── 天气图标映射 ──────────────────────────────────────────
WEATHER_ICONS = {
    "113": "☀️", "116": "🌤️", "119": "☁️", "122": "🌌️", "143": "🌗️",
    "176": "🌦️", "179": "🌐️", "182": "🌫️", "185": "🌫️", "200": "⛈️",
    "227": "🌙️", "230": "❄️", "248": "🌗️", "260": "🌗️", "263": "🌦️",
    "266": "🌫️", "281": "🌫️", "284": "🌫️", "293": "🌦️", "296": "🌫️",
    "299": "🌫️", "302": "🌫️", "305": "🌫️", "308": "🌫️", "311": "🌐️",
    "314": "🌐️", "317": "🌐️", "320": "🌐️", "323": "❄️", "326": "❄️",
    "329": "❄️", "332": "🌗️", "335": "🌐️", "338": "🌐️", "350": "🌐️",
    "353": "🌦️", "356": "🌫️", "359": "🌫️", "362": "🌫️", "365": "🌫️",
    "368": "🌐️", "371": "🌐️", "374": "🌐️", "377": "🌐️", "386": "⛈️",
    "389": "⛈️", "392": "⛈️", "395": "🌐️",
}

WIND_CN = {
    "N": "北", "NNE": "东北偏北", "NE": "东北", "ENE": "东北偏东",
    "E": "东", "ESE": "东南偏东", "SE": "东南", "SSE": "东南偏南",
    "S": "南", "SSW": "西南偏南", "SW": "西南", "WSW": "西南偏西",
    "W": "西", "WNW": "西北偏西", "NW": "西北", "NNW": "西北偏北",
}


def fetch_weather(city):
    """从 wttr.in 获取指定城市天气 JSON"""
    url = f"https://wttr.in/{city}?format=j1&lang=zh"
    log.info("Fetching weather for: %s", city)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data



# ── 天气描述中英对照 (wttr.in JSON API 始终返回英文，此处做转换) ──
WEATHER_DESC_CN = {
    "Sunny": "晴",
    "Clear": "晴",
    "Partly Cloudy": "多云",
    "Partly cloudy": "多云",
    "Cloudy": "阴",
    "Overcast": "阴",
    "Mist": "薄雾",
    "Fog": "雾",
    "Freezing fog": "冻雾",
    "Patchy rain possible": "局部阵雨",
    "Patchy rain nearby": "局部阵雨",
    "Patchy light rain": "局部小雨",
    "Light rain": "小雨",
    "Moderate rain": "中雨",
    "Moderate rain at times": "间歇中雨",
    "Heavy rain": "大雨",
    "Heavy rain at times": "间歇大雨",
    "Light freezing rain": "小冻雨",
    "Moderate or heavy freezing rain": "中到大冻雨",
    "Light drizzle": "小毛毛雨",
    "Patchy light drizzle": "局部毛毛雨",
    "Light rain shower": "小阵雨",
    "Moderate or heavy rain shower": "中到大阵雨",
    "Torrential rain shower": "暴雨",
    "Light sleet": "小雨夹雪",
    "Moderate or heavy sleet": "中到大雨夹雪",
    "Light sleet showers": "小阵雨夹雪",
    "Moderate or heavy sleet showers": "中到大阵雨夹雪",
    "Light snow": "小雪",
    "Patchy light snow": "局部小雪",
    "Moderate snow": "中雪",
    "Patchy moderate snow": "局部中雪",
    "Heavy snow": "大雪",
    "Patchy heavy snow": "局部大雪",
    "Light snow showers": "小阵雪",
    "Moderate or heavy snow showers": "中到大阵雪",
    "Blowing snow": "吹雪",
    "Blizzard": "暴风雪",
    "Ice pellets": "冰粒",
    "Light showers of ice pellets": "小阵冰粒",
    "Moderate or heavy showers of ice pellets": "中到大阵冰粒",
    "Thundery outbreaks possible": "可能有雷暴",
    "Thundery outbreaks nearby": "附近有雷暴",
    "Patchy light rain with thunder": "局部小雷雨",
    "Moderate or heavy rain with thunder": "中到大雷雨",
    "Patchy light snow with thunder": "局部小雷雪",
    "Moderate or heavy snow with thunder": "中到大雷雪",
}

def translate_desc(desc):
    """将英文天气描述转为中文"""
    return WEATHER_DESC_CN.get(desc, desc)

def build_suggestion(temp_c, weather_code):
    """根据温度和天气码生成生活建议"""
    temp = int(temp_c)
    lines = []
    if temp >= 35:
        lines.append("🔥 高温预警！注意防暑降温，多喝水，避免长时间户外活动。")
    elif temp >= 30:
        lines.append("☀️ 天气较热，建议穿轻薄衣物，注意防晒。")
    elif temp >= 20:
        lines.append("😉 温度舒适，适合户外活动。")
    elif temp >= 10:
        lines.append("🍅 天气凉爽，建议穿薄外套。")
    elif temp >= 0:
        lines.append("❄️ 天气寒冷，注意保暖。")
    else:
        lines.append("🧊 天气严寒，请穿厚外套，注意防冻。")

    wc = str(weather_code)
    if wc in ("176","263","266","293","296","299","302","305","308","353","356","359"):
        lines.append("🌫️ 今天有雨，出门请带伞！")
    return " ".join(lines)
