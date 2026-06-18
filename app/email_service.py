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
                'style="width:100%;max-width:576px;display:block;margin:0 auto;border-radius:8px;border:1px solid #e4dfd7;" '
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
            f"<td class='td-time'>{hour_str}</td>"
            f"<td>{h_icon} {h_desc}</td>"
            f"<td class='td-num'>{h_temp}°C</td>"
            f"<td class='td-num'>{h_rain}%</td>"
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
            f"<td class='td-time'>{day_label}</td>"
            f"<td>{d_icon} {d_desc}</td>"
            f"<td class='td-num'>{day_max}°C</td>"
            f"<td class='td-num'>{day_min}°C</td>"
            f"<td class='td-num'>{d_rain}%</td>"
            f"</tr>"
        )
    html = f"""<!DOCTYPE html>
<html lang=zh-CN>
<head>
<meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>{city_name}天气日报</title>
<style>
    body {{ margin:0; padding:0; background:#f4f1ec; font-family:'Microsoft YaHei','PingFang SC','Segoe UI',Arial,sans-serif; color:#24272b; }}
    .shell {{ width:100%; background:#f4f1ec; padding:28px 0; }}
    .container {{ max-width:640px; margin:0 auto; background:#ffffff; border:1px solid #e4dfd7; border-radius:8px; overflow:hidden; }}
    .header {{ padding:28px 32px 22px; border-bottom:1px solid #ece7df; }}
    .kicker {{ margin:0 0 8px; font-size:12px; letter-spacing:1.6px; color:#6c817d; font-weight:700; text-transform:uppercase; }}
    .title {{ margin:0; font-size:24px; line-height:1.25; color:#1f2328; font-weight:700; }}
    .date {{ margin-top:8px; font-size:13px; color:#747b84; }}
    .hero {{ padding:30px 32px 24px; }}
    .hero-table {{ width:100%; border-collapse:collapse; }}
    .hero-icon {{ width:96px; font-size:58px; line-height:1; vertical-align:middle; }}
    .temperature {{ margin:0; font-size:58px; line-height:1; color:#1f2328; font-weight:300; letter-spacing:0; }}
    .weather-desc {{ margin-top:8px; font-size:15px; color:#5d646d; }}
    .pill {{ display:inline-block; margin-top:12px; padding:6px 10px; border-radius:999px; background:#edf4f2; color:#2f5f5b; font-size:12px; font-weight:700; }}
    .details {{ width:calc(100% - 64px); margin:0 32px 8px; border-collapse:separate; border-spacing:0 10px; }}
    .detail-item {{ width:50%; padding:14px 16px; background:#fbfaf8; border-top:1px solid #ece7df; border-bottom:1px solid #ece7df; }}
    .detail-left {{ border-left:1px solid #ece7df; border-radius:8px 0 0 8px; }}
    .detail-right {{ border-right:1px solid #ece7df; border-radius:0 8px 8px 0; }}
    .detail-label {{ font-size:12px; color:#8b929b; margin-bottom:4px; }}
    .detail-value {{ font-size:15px; color:#24272b; font-weight:700; }}
    .chart-section {{ padding:18px 32px 8px; }}
    .section {{ padding:18px 32px 4px; }}
    .section-title {{ margin:0 0 10px; font-size:15px; color:#1f2328; font-weight:700; }}
    .forecast-table {{ width:100%; border-collapse:collapse; border:1px solid #e8e3dc; border-radius:8px; overflow:hidden; }}
    .forecast-table th {{ background:#f7f5f1; padding:10px 12px; text-align:left; font-size:12px; color:#777f88; font-weight:700; border-bottom:1px solid #e8e3dc; }}
    .forecast-table td {{ padding:10px 12px; font-size:13px; color:#34383e; border-bottom:1px solid #efebe5; }}
    .forecast-table tr:last-child td {{ border-bottom:none; }}
    .td-time {{ color:#6f777f; white-space:nowrap; }}
    .td-num {{ text-align:right; white-space:nowrap; }}
    .suggestion {{ margin:22px 32px 26px; padding:16px 18px; background:#f7f5f1; border:1px solid #e4dfd7; border-left:4px solid #6c817d; border-radius:8px; font-size:14px; color:#4c535b; line-height:1.8; }}
    .footer {{ padding:18px 32px 24px; text-align:center; font-size:12px; color:#9aa0a8; border-top:1px solid #ece7df; }}
    @media only screen and (max-width:680px) {{
        .shell {{ padding:0; }}
        .container {{ width:100%; border-radius:0; border-left:none; border-right:none; }}
        .header, .hero, .section, .chart-section, .footer {{ padding-left:20px; padding-right:20px; }}
        .details {{ width:calc(100% - 40px); margin-left:20px; margin-right:20px; }}
        .temperature {{ font-size:48px; }}
        .hero-icon {{ width:72px; font-size:46px; }}
        .suggestion {{ margin-left:20px; margin-right:20px; }}
    }}
</style>
</head>
<body>
<div class=shell>
<div class=container>
    <div class=header>
        <div class=kicker>Daily Weather Brief</div>
        <h1 class=title>{city_name}天气日报</h1>
        <div class=date>{today_str}</div>
    </div>
    <div class=hero>
        <table class=hero-table role=presentation>
            <tr>
                <td class=hero-icon>{weather_icon}</td>
                <td>
                    <div class=temperature>{temp_c}°C</div>
                    <div class=weather-desc>{weather_desc} · 体感 {feels}°C</div>
                    <div class=pill>每天 {send_hour:02d}:{send_minute:02d} 自动发送</div>
                </td>
            </tr>
        </table>
    </div>
    {chart_html}
    <table class=details role=presentation>
        <tr>
            <td class='detail-item detail-left'><div class=detail-label>最高 / 最低</div><div class=detail-value>{max_temp}°C / {min_temp}°C</div></td>
            <td class='detail-item detail-right'><div class=detail-label>湿度</div><div class=detail-value>{humidity}%</div></td>
        </tr>
        <tr>
            <td class='detail-item detail-left'><div class=detail-label>风向 / 风速</div><div class=detail-value>{wind_cn} · {wind_speed} km/h</div></td>
            <td class='detail-item detail-right'><div class=detail-label>能见度</div><div class=detail-value>{visibility} km</div></td>
        </tr>
        <tr>
            <td class='detail-item detail-left'><div class=detail-label>紫外线指数</div><div class=detail-value>{uv}</div></td>
            <td class='detail-item detail-right'><div class=detail-label>日出 / 日落</div><div class=detail-value>{sunrise} / {sunset}</div></td>
        </tr>
    </table>
    <div class=section>
        <h2 class=section-title>逐小时预报</h2>
        <table class=forecast-table>
            <tr><th>时间</th><th>天气</th><th class=td-num>温度</th><th class=td-num>降雨</th></tr>
            {hourly_rows}
        </table>
    </div>
    <div class=section>
        <h2 class=section-title>未来几日天气</h2>
        <table class=forecast-table>
            <tr><th>日期</th><th>天气</th><th class=td-num>最高</th><th class=td-num>最低</th><th class=td-num>降雨</th></tr>
            {future_rows}
        </table>
    </div>
    <div class=suggestion>{suggestion_text}</div>
    <div class=footer>数据来源: wttr.in · weather-email</div>
</div>
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
