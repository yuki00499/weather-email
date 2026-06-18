# -*- coding: utf-8 -*-
"""邮件服务模块 - HTML 模板构建 + SMTP 发送"""

import smtplib
import logging
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

import pytz

from app.weather import WEATHER_ICONS, WIND_CN, build_suggestion, translate_desc
from app.chart import build_temperature_chart

log = logging.getLogger(__name__)

TZ = pytz.timezone("Asia/Hong_Kong")

WEEKDAY_CN = {"Monday": "周一", "Tuesday": "周二", "Wednesday": "周三", "Thursday": "周四", "Friday": "周五", "Saturday": "周六", "Sunday": "周日"}


def build_html(data, config):
    """构建天气 HTML 邮件 (城市名、发送时间等从 config 注入)"""
    city_name = config.get("city_display_name", "无锡")
    send_hour = int(config.get("send_hour", 8))
    send_minute = int(config.get("send_minute", 0))

    current = data["current_condition"][0]
    weather = data["weather"][0]
    astronomy = weather["astronomy"][0]
    hourly = weather["hourly"]

    weather_code = current["weatherCode"]
    weather_icon = WEATHER_ICONS.get(weather_code, "🌅️")
    weather_desc = translate_desc(current["weatherDesc"][0]["value"])
    temp_c = current["temp_C"]
    feels = current["FeelsLikeC"]
    humidity = current["humidity"]
    wind_dir = current["winddir16Point"]
    wind_cn = WIND_CN.get(wind_dir, wind_dir)
    wind_speed = current["windspeedKmph"]
    visibility = current["visibility"]
    uv = current["uvIndex"]
    max_temp = weather["maxtempC"]
    min_temp = weather["mintempC"]
    sunrise = astronomy["sunrise"]
    sunset = astronomy["sunset"]
    now = datetime.now(TZ)
    today_str = now.strftime("%Y-%m-%d") + " " + WEEKDAY_CN.get(now.strftime("%A"), now.strftime("%A"))

    suggestion_text = build_suggestion(temp_c, weather_code)

    # ── 生成气温趋势图表 ──
    chart_html = ""
    try:
        chart_b64 = build_temperature_chart(data)
        if chart_b64:
            chart_html = (
                '<div class="chart-section">'
                '<img src="data:image/png;base64,' + chart_b64 + '" '
                'style="width:100%;max-width:560px;display:block;margin:0 auto;border-radius:12px;" '
                'alt="气温趋势图">'
                '</div>'
            )
        else:
            log.warning("Chart generation returned no data, skipping chart in email")
    except Exception as exc:
        log.warning("Failed to generate temperature chart: %s", exc)

    hourly_rows = ""
    for h in hourly:
        hour_str = f"{int(h['time']) // 100:02d}:00"
        h_icon = WEATHER_ICONS.get(h["weatherCode"], "🌅️")
        h_desc = translate_desc(h["weatherDesc"][0]["value"])
        h_temp = h["tempC"]
        h_rain = h["chanceofrain"]
        hourly_rows += (
            f"<tr>"
            f"<td>{hour_str}</td>"
            f"<td>{h_icon} {h_desc}</td>"
            f"<td>{h_temp}°C</td>"
            f"<td>{h_rain}%</td>"
            f"</tr>"
        )


    # 未来几日天气表格
    future_rows = ""
    future_days = data.get("weather", [])[1:]
    for day in future_days:
        day_date = day.get("date", "")
        try:
            dt = datetime.strptime(day_date, "%Y-%m-%d")
            day_label = f"{dt.month}月{dt.day}日 " + WEEKDAY_CN.get(dt.strftime("%A"), dt.strftime("%A"))
        except (ValueError, TypeError):
            day_label = day_date
        day_max = day.get("maxtempC", "")
        day_min = day.get("mintempC", "")
        day_hourly = day.get("hourly", [])
        rep = day_hourly[0] if day_hourly else {}
        for h in day_hourly:
            try:
                htime = int(h.get("time", 0))
            except (ValueError, TypeError):
                htime = 0
            if htime in (1100, 1200, 1300, 1400):
                rep = h
                break
        d_icon = WEATHER_ICONS.get(rep.get("weatherCode", ""), "☀️")
        d_desc = ""
        if rep.get("weatherDesc"):
            d_desc = translate_desc(rep["weatherDesc"][0]["value"])
        d_rain = rep.get("chanceofrain", "")
        future_rows += (
            f"<tr>"
            f"<td>{day_label}</td>"
            f"<td>{d_icon} {d_desc}</td>"
            f"<td>{day_max}°C</td>"
            f"<td>{day_min}°C</td>"
            f"<td>{d_rain}%</td>"
            f"</tr>"
        )
    html = f"""<!DOCTYPE html>
<html lang=zh-CN>
<head>
<meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>{city_name}天气日报</title>
<style>
    body {{ margin:0; padding:0; background:#f5f7fa; font-family:'Microsoft YaHei','PingFang SC',sans-serif; }}
    .container {{ max-width:600px; margin:20px auto; background:#fff; border-radius:16px; overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,0.08); }}
    .header {{ background:linear-gradient(135deg,#4facfe 0%,#00f2fe 100%); padding:30px; text-align:center; color:#fff; }}
    .header h1 {{ margin:0; font-size:22px; font-weight:500; }}
    .header .date {{ font-size:13px; opacity:0.85; margin-top:6px; }}
    .weather-card {{ text-align:center; padding:30px; }}
    .weather-icon {{ font-size:64px; }}
    .temperature {{ font-size:56px; font-weight:300; color:#333; margin:10px 0; }}
    .weather-desc {{ font-size:15px; color:#888; }}
    .chart-section {{ padding:0 20px 10px; }}
    .details {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; padding:0 30px 20px; }}
    .detail-item {{ background:#f8fafc; border-radius:12px; padding:14px; }}
    .detail-label {{ font-size:12px; color:#aaa; margin-bottom:4px; }}
    .detail-value {{ font-size:16px; color:#333; font-weight:500; }}
    .section-title {{ padding:10px 30px; font-size:15px; color:#555; font-weight:500; }}
    .hourly-table {{ width:calc(100% - 60px); border-collapse:collapse; margin:0 30px 10px; }}
    .hourly-table th {{ background:#f0f2f8; padding:8px 12px; text-align:left; font-size:12px; color:#999; }}
    .hourly-table td {{ padding:8px 12px; font-size:13px; color:#555; border-bottom:1px solid #f0f0f0; }}
    .suggestion {{ margin:20px 30px; padding:16px 20px; background:#fff8e6; border-left:4px solid #ffc107; border-radius:8px; font-size:14px; color:#666; line-height:1.8; }}
    .footer {{ text-align:center; padding:20px 30px; font-size:12px; color:#ccc; border-top:1px solid #f0f0f0; }}
</style>
</head>
<body>
<div class=container>
    <div class=header>
        <h1>🌇️ {city_name}天气日报</h1>
        <div class=date>{today_str}</div>
    </div>
    <div class=weather-card>
        <div class=weather-icon>{weather_icon}</div>
        <div class=temperature>{temp_c}°C</div>
        <div class=weather-desc>体感 {feels}°C · {weather_desc}</div>
    </div>
    {chart_html}
    <div class=details>
        <div class=detail-item><div class=detail-label>最高 / 最低</div><div class=detail-value>{max_temp}°C / {min_temp}°C</div></div>
        <div class=detail-item><div class=detail-label>湿度</div><div class=detail-value>{humidity}%</div></div>
        <div class=detail-item><div class=detail-label>风向 / 风速</div><div class=detail-value>{wind_cn} · {wind_speed} km/h</div></div>
        <div class=detail-item><div class=detail-label>能见度</div><div class=detail-value>{visibility} km</div></div>
        <div class=detail-item><div class=detail-label>紫外线指数</div><div class=detail-value>{uv}</div></div>
        <div class=detail-item><div class=detail-label>日出 / 日落</div><div class=detail-value>{sunrise} / {sunset}</div></div>
    </div>
    <div class=section-title>⏰ 逐小时预报</div>
    <table class=hourly-table>
        <tr><th>时间</th><th>天气</th><th>温度</th><th>降雨概率</th></tr>
        {hourly_rows}
    </table>
    <div class=section-title>📅 未来几日天气</div>
    <table class=hourly-table>
        <tr><th>日期</th><th>天气</th><th>最高温</th><th>最低温</th><th>降雨概率</th></tr>
        {future_rows}
    </table>
    <div class=section-title>💡 生活建议</div>
    <div class=suggestion>{suggestion_text}</div>
    <div class=footer>数据来源: wttr.in · 每天 {send_hour:02d}:{send_minute:02d} 自动发送</div>
</div>
</body>
</html>"""
    return html


def send_email(config, html_body, subject_extra=""):
    """发送 HTML 邮件"""
    today_str = datetime.now(TZ).strftime("%Y-%m-%d")
    subject_prefix = config.get("subject_prefix", "[天气日报]")

    smtp_from = config["smtp_from"]
    smtp_from_name = config.get("smtp_from_name", "天气助手")
    email_to = config["email_to"]
    recipients = [addr.strip() for addr in email_to.split(",") if addr.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(f"{subject_prefix} {today_str} {subject_extra}", "utf-8")
    msg["From"] = formataddr((smtp_from_name, smtp_from))
    msg["To"] = email_to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    use_ssl = config.get("smtp_use_ssl", "true").lower() == "true"
    smtp_server = config["smtp_server"]
    smtp_port = int(config["smtp_port"])

    if use_ssl:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
    else:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        server.starttls()

    server.login(config["smtp_username"], config["smtp_password"])
    server.sendmail(smtp_from, recipients, msg.as_string())
    server.quit()
