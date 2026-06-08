# -*- coding: utf-8 -*-
"""weather-email Web UI + 定时任务主入口"""

import logging
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from app.models import init_db, get_all_configs, save_configs, get_config
from app.weather import fetch_weather, WEATHER_ICONS
from app.email_service import build_html, send_email

TZ = pytz.timezone("Asia/Hong_Kong")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = "weather-email-secret-key-change-in-production"

scheduler = BackgroundScheduler(timezone=TZ)


# ── 核心任务 ──────────────────────────────────────────────

def send_weather_job():
    """定时任务：获取天气并发送邮件"""
    config = get_all_configs()
    city = config.get("city", "Wuxi")
    city_name = config.get("city_display_name", "无锡")

    log.info("🌍️ 开始获取 %s 天气...", city_name)
    try:
        data = fetch_weather(city)
        current = data["current_condition"][0]
        weather_icon = WEATHER_ICONS.get(current["weatherCode"], "🌅️")
        weather_desc = current["weatherDesc"][0]["value"]
        temp_c = current["temp_C"]

        html = build_html(data, config)
        send_email(config, html,
                   subject_extra=f"· {weather_icon} {weather_desc} {temp_c}°C")
        log.info("✅ 邮件发送成功 - %s %s°C", weather_desc, temp_c)
        return True, f"{weather_desc} {temp_c}°C"
    except Exception as e:
        log.error("❌ 任务失败: %s", e)
        return False, str(e)


def reschedule_job():
    """根据当前配置重新调度定时任务"""
    config = get_all_configs()
    hour = int(config.get("send_hour", 8))
    minute = int(config.get("send_minute", 0))

    scheduler.remove_all_jobs()
    scheduler.add_job(
        send_weather_job,
        CronTrigger(hour=hour, minute=minute, timezone=TZ),
        id="weather_email",
        name="Weather Email Daily Job",
        replace_existing=True,
    )
    log.info("⏰ 定时任务已更新: 每天 %02d:%02d", hour, minute)


# ── Flask 路由 ────────────────────────────────────────────

@app.route("/")
def index():
    """仪表盘"""
    config = get_all_configs()
    job = scheduler.get_job("weather_email")
    next_run = job.next_run_time.astimezone(TZ).strftime("%Y-%m-%d %H:%M") if job else "未设置"
    return render_template("index.html", config=config, next_run=next_run)


@app.route("/config", methods=["GET", "POST"])
def config_page():
    """配置编辑页"""
    if request.method == "POST":
        data = {
            "smtp_server": request.form.get("smtp_server", ""),
            "smtp_port": request.form.get("smtp_port", "465"),
            "smtp_use_ssl": request.form.get("smtp_use_ssl", "true"),
            "smtp_username": request.form.get("smtp_username", ""),
            "smtp_password": request.form.get("smtp_password", ""),
            "smtp_from": request.form.get("smtp_from", ""),
            "smtp_from_name": request.form.get("smtp_from_name", "天气助手"),
            "email_to": request.form.get("email_to", ""),
            "subject_prefix": request.form.get("subject_prefix", "[天气日报]"),
            "send_hour": request.form.get("send_hour", "8"),
            "send_minute": request.form.get("send_minute", "0"),
            "city": request.form.get("city", "Wuxi"),
            "city_display_name": request.form.get("city_display_name", "无锡"),
        }
        save_configs(data)
        reschedule_job()
        flash("✅ 配置已保存，定时任务已更新", "success")
        return redirect(url_for("index"))

    config = get_all_configs()
    return render_template("config.html", config=config)


@app.route("/send-now", methods=["POST"])
def send_now():
    """手动立即发送"""
    success, detail = send_weather_job()
    if success:
        flash(f"✅ 邮件已发送！天气: {detail}", "success")
    else:
        flash(f"❌ 发送失败: {detail}", "error")
    return redirect(url_for("index"))


# ── 启动 ──────────────────────────────────────────────────

def main():
    log.info("🚀 weather-email 服务启动")
    init_db()
    reschedule_job()
    scheduler.start()
    log.info("🌐 Web UI: http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()
