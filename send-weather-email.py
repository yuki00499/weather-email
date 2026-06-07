#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""无锡天气日报 - Docker 部署版
每天 08:00 (Asia/Hong_Kong) 自动获取天气并发送邮件
"""

import os
import smtplib
import logging
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

import requests
import schedule
import time
import pytz

# ── 配置 (从环境变量读取) ──────────────────────────
TZ = pytz.timezone("Asia/Hong_Kong")

SMTP_CONFIG = {
    "server":   os.getenv("SMTP_SERVER", "smtp.qq.com"),
    "port":     int(os.getenv("SMTP_PORT", "587")),
    "use_ssl":  os.getenv("SMTP_USE_SSL", "true").lower() == "true",
    "username": os.getenv("SMTP_USERNAME", ""),
    "password": os.getenv("SMTP_PASSWORD", ""),
    "from_addr": os.getenv("SMTP_FROM", ""),
    "from_name": os.getenv("SMTP_FROM_NAME", "天气助手"),
}

EMAIL_TO = os.getenv("EMAIL_TO", "")
SUBJECT_PREFIX = os.getenv("SUBJECT_PREFIX", "[无锡天气]")
SEND_HOUR = int(os.getenv("SEND_HOUR", "8"))
SEND_MINUTE = int(os.getenv("SEND_MINUTE", "0"))

# ── 日志 ───────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


# ── 天气图标映射 ───────────────────────────────────
WEATHER_ICONS = {
    "113": "☀️", "116": "🌤️", "119": "☁️", "122": "🌥️", "143": "🌫️",
    "176": "🌦️", "179": "🌨️", "182": "🌧️", "185": "🌧️", "200": "⛈️",
    "227": "🌬️", "230": "❄️", "248": "🌫️", "260": "🌫️", "263": "🌦️",
    "266": "🌧️", "281": "🌧️", "284": "🌧️", "293": "🌦️", "296": "🌧️",
    "299": "🌧️", "302": "🌧️", "305": "🌧️", "308": "🌧️", "311": "🌨️",
    "314": "🌨️", "317": "🌨️", "320": "🌨️", "323": "❄️", "326": "❄️",
    "329": "❄️", "332": "🌫️", "335": "🌨️", "338": "🌨️", "350": "🌨️",
    "353": "🌦️", "356": "🌧️", "359": "🌧️", "362": "🌧️", "365": "🌧️",
    "368": "🌨️", "371": "🌨️", "374": "🌨️", "377": "🌨️", "386": "⛈️",
    "389": "⛈️", "392": "⛈️", "395": "🌨️",
}

WIND_CN = {
    "N": "北", "NNE": "东北偏北", "NE": "东北", "ENE": "东北偏东",
    "E": "东", "ESE": "东南偏东", "SE": "东南", "SSE": "东南偏南",
    "S": "南", "SSW": "西南偏南", "SW": "西南", "WSW": "西南偏西",
    "W": "西", "WNW": "西北偏西", "NW": "西北", "NNW": "西北偏北",
}

def fetch_weather():
    """从 wttr.in 获取无锡天气 JSON"""
    url = "https://wttr.in/Wuxi?format=j1"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def build_suggestion(temp_c, weather_code):
    temp_c = int(temp_c)
    """生成生活建议"""
    lines = []
    if temp_c >= 35:
        lines.append("🔥 高温预警！注意防暑降温，多喝水，避免长时间户外活动。")
    elif temp_c >= 30:
        lines.append("☀️ 天气较热，建议穿轻薄衣物，注意防晒。")
    elif temp_c >= 20:
        lines.append("😊 温度舒适，适合户外活动。")
    elif temp_c >= 10:
        lines.append("🍂 天气凉爽，建议穿薄外套。")
    elif temp_c >= 0:
        lines.append("❄️ 天气寒冷，注意保暖。")
    else:
        lines.append("🥶 天气严寒，请穿厚外套，注意防冻。")

    wc = str(weather_code)
    if wc in ("176","263","266","293","296","299","302","305","308","353","356","359"):
        lines.append("🌧️ 今天有雨，出门请带伞！")
    elif wc in ("179","227","230","311","314","317","320","323","326","329",
                 "335","338","350","362","365","368","371","374","377","392","395"):
        lines.append("🌨️ 今天有雪，注意路面安全！")
    return "<br>".join(lines)

def build_html(data):
    """根据天气数据生成 HTML 邮件"""
    current = data["current_condition"][0]
    forecast = data["weather"][0]
    today_str = datetime.now(TZ).strftime("%Y-%m-%d")

    temp_c = current["temp_C"]
    feels = current["FeelsLikeC"]
    humidity = current["humidity"]
    wind_speed = current["windspeedKmph"]
    wind_dir = current["winddir16Point"]
    visibility = current["visibility"]
    uv = current["uvIndex"]
    weather_code = current["weatherCode"]
    weather_desc = current["weatherDesc"][0]["value"]
    weather_icon = WEATHER_ICONS.get(weather_code, "🌡️")

    max_temp = forecast["maxtempC"]
    min_temp = forecast["mintempC"]
    sunrise = forecast["astronomy"][0]["sunrise"]
    sunset = forecast["astronomy"][0]["sunset"]
    wind_cn = WIND_CN.get(wind_dir, wind_dir)

    # 逐小时预报
    hourly_rows = ""
    for h in forecast["hourly"]:
        hour = int(h["time"]) // 100
        hic = WEATHER_ICONS.get(h["weatherCode"], "")
        hdesc = h["weatherDesc"][0]["value"]
        htemp = h["tempC"]
        hrain = h.get("chanceofrain", "N/A")
        hourly_rows += f"<tr><td>{hour:02d}:00</td><td>{hic} {hdesc}</td><td>{htemp}&#176;C</td><td>{hrain}</td></tr>"

    suggestion = build_suggestion(temp_c, weather_code)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>无锡天气日报 - {today_str}</title>
<style>
    body {{ margin:0; padding:0; background:#f5f6fa; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
    .container {{ max-width:600px; margin:0 auto; background:#fff; border-radius:12px; overflow:hidden; }}
    .header {{ background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:#fff; padding:28px 30px; text-align:center; }}
    .header h1 {{ margin:0; font-size:24px; font-weight:600; }}
    .header .date {{ margin-top:6px; font-size:14px; opacity:.85; }}
    .weather-card {{ text-align:center; padding:24px 30px; }}
    .weather-icon {{ font-size:56px; }}
    .temperature {{ font-size:52px; font-weight:700; color:#333; }}
    .weather-desc {{ font-size:14px; color:#999; margin-top:4px; }}
    .details {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; padding:0 30px 20px; }}
    .detail-item {{ padding:12px 16px; background:#f8f9fc; border-radius:8px; }}
    .detail-label {{ font-size:12px; color:#999; margin-bottom:2px; }}
    .detail-value {{ font-size:16px; color:#333; font-weight:500; }}
    .section-title {{ padding:20px 30px 10px; font-size:16px; font-weight:600; color:#333; }}
    .hourly-table {{ width:calc(100% - 60px); border-collapse:collapse; margin:0 30px 10px; }}
    .hourly-table th {{ background:#f0f2f8; padding:8px 12px; text-align:left; font-size:12px; color:#999; }}
    .suggestion {{ margin:20px 30px; padding:16px 20px; background:#fff8e6; border-left:4px solid #ffc107; border-radius:8px; font-size:14px; color:#666; line-height:1.8; }}
    .footer {{ text-align:center; padding:20px 30px; font-size:12px; color:#ccc; border-top:1px solid #f0f0f0; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🏙️ 无锡天气日报</h1>
        <div class="date">{today_str}</div>
    </div>
    <div class="weather-card">
        <div class="weather-icon">{weather_icon}</div>
        <div class="temperature">{temp_c}°C</div>
        <div class="weather-desc">体感 {feels}°C · {weather_desc}</div>
    </div>
    <div class="details">
        <div class="detail-item"><div class="detail-label">最高 / 最低</div><div class="detail-value">{max_temp}°C / {min_temp}°C</div></div>
        <div class="detail-item"><div class="detail-label">湿度</div><div class="detail-value">{humidity}%</div></div>
        <div class="detail-item"><div class="detail-label">风向 / 风速</div><div class="detail-value">{wind_cn} · {wind_speed} km/h</div></div>
        <div class="detail-item"><div class="detail-label">能见度</div><div class="detail-value">{visibility} km</div></div>
        <div class="detail-item"><div class="detail-label">紫外线指数</div><div class="detail-value">{uv}</div></div>
        <div class="detail-item"><div class="detail-label">日出 / 日落</div><div class="detail-value">{sunrise} / {sunset}</div></div>
    </div>
    <div class="section-title">⏰ 逐小时预报</div>
    <table class="hourly-table">
        <tr><th>时间</th><th>天气</th><th>温度</th><th>降雨概率</th></tr>
        {hourly_rows}
    </table>
    <div class="section-title">💡 生活建议</div>
    <div class="suggestion">{suggestion}</div>
    <div class="footer">数据来源: wttr.in · 每天早上 {SEND_HOUR}:{SEND_MINUTE:02d} 自动发送</div>
</div>
</body>
</html>"""
    return html

def send_email(html_body, subject_extra=""):
    """发送 HTML 邮件"""
    today_str = datetime.now(TZ).strftime("%Y-%m-%d")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(f"{SUBJECT_PREFIX} {today_str} {subject_extra}", "utf-8")
    msg["From"] = formataddr((SMTP_CONFIG["from_name"], SMTP_CONFIG["from_addr"]))
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if SMTP_CONFIG["use_ssl"]:
        server = smtplib.SMTP_SSL(SMTP_CONFIG["server"], SMTP_CONFIG["port"], timeout=30)
    else:
        server = smtplib.SMTP(SMTP_CONFIG["server"], SMTP_CONFIG["port"], timeout=30)
        server.starttls()

    server.login(SMTP_CONFIG["username"], SMTP_CONFIG["password"])
    server.sendmail(SMTP_CONFIG["from_addr"], EMAIL_TO, msg.as_string())
    server.quit()


def job():
    """定时任务：获取天气并发送邮件"""
    log.info("🌤️ 开始获取无锡天气...")
    try:
        data = fetch_weather()
        current = data["current_condition"][0]
        weather_icon = WEATHER_ICONS.get(current["weatherCode"], "🌡️")
        weather_desc = current["weatherDesc"][0]["value"]
        temp_c = current["temp_C"]

        html = build_html(data)
        send_email(html, subject_extra=f"· {weather_icon} {weather_desc} {temp_c}°C")
        log.info("✅ 邮件发送成功 - %s %s°C", weather_desc, temp_c)
    except Exception as e:
        log.error("❌ 任务失败: %s", e)


def main():
    # 验证必要配置
    required = ["SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM", "EMAIL_TO"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        log.error("缺少必要的环境变量: %s", ", ".join(missing))
        log.info("请参考 .env.example 配置环境变量")
        exit(1)

    log.info("🚀 无锡天气邮件服务启动")
    log.info("   发送时间: 每天 %02d:%02d (Asia/Hong_Kong)", SEND_HOUR, SEND_MINUTE)
    log.info("   收件人: %s", EMAIL_TO)

    # 启动时立即发送一次（方便测试）
    log.info("📤 启动测试：立即发送一封...")
    job()

    # 注册定时任务
    schedule.every().day.at(f"{SEND_HOUR:02d}:{SEND_MINUTE:02d}", TZ).do(job)
    log.info("⏰ 定时任务已注册，等待下次触发...")

    # 主循环
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()