# -*- coding: utf-8 -*-
"""weather-email Web UI and multi-task scheduler."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask, flash, redirect, render_template, request, url_for
import pytz

from app.email_service import build_html, send_email
from app.models import (
    TASK_DEFAULTS,
    create_task,
    delete_task,
    get_task,
    init_db,
    list_enabled_tasks,
    list_tasks,
    update_task,
)
from app.weather import WEATHER_ICONS, fetch_weather

TZ = pytz.timezone("Asia/Hong_Kong")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = "weather-email-secret-key-change-in-production"

scheduler = BackgroundScheduler(timezone=TZ)


# ── Core jobs ─────────────────────────────────────────────

def send_weather_job(task_id):
    """Fetch weather and send the configured email for one task."""
    task = get_task(task_id)
    if not task:
        detail = f"任务 {task_id} 不存在"
        log.warning(detail)
        return False, detail

    city = task.get("city", "Wuxi")
    city_name = task.get("city_display_name", "无锡")
    task_name = task.get("name", f"任务 {task_id}")

    log.info("Start weather task %s for %s", task_name, city_name)
    try:
        data = fetch_weather(city)
        current = data["current_condition"][0]
        weather_icon = WEATHER_ICONS.get(current["weatherCode"], "")
        weather_desc = current["weatherDesc"][0]["value"]
        temp_c = current["temp_C"]

        html = build_html(data, task)
        send_email(
            task,
            html,
            subject_extra=f"· {weather_icon} {weather_desc} {temp_c}°C",
        )
        detail = f"{weather_desc} {temp_c}°C"
        log.info("Weather task sent successfully: %s - %s", task_name, detail)
        return True, detail
    except Exception as exc:
        log.error("Weather task failed: %s - %s", task_name, exc)
        return False, str(exc)


def reschedule_jobs():
    """Rebuild all scheduler jobs from enabled tasks."""
    scheduler.remove_all_jobs()
    for task in list_enabled_tasks():
        hour = int(task.get("send_hour", 8))
        minute = int(task.get("send_minute", 0))
        scheduler.add_job(
            send_weather_job,
            CronTrigger(hour=hour, minute=minute, timezone=TZ),
            args=[task["id"]],
            id=_job_id(task["id"]),
            name=f"Weather Email - {task.get('name', task['id'])}",
            replace_existing=True,
        )
        log.info(
            "Scheduled task %s at %02d:%02d",
            task.get("name", task["id"]),
            hour,
            minute,
        )


def _job_id(task_id):
    return f"weather_email_{task_id}"


# ── Flask routes ──────────────────────────────────────────

@app.route("/")
def index():
    """Task dashboard."""
    tasks = []
    next_runs = []
    for task in list_tasks():
        job = scheduler.get_job(_job_id(task["id"]))
        next_run = _format_next_run(job)
        task["next_run"] = next_run
        if next_run != "未设置":
            next_runs.append(next_run)
        tasks.append(task)

    stats = {
        "total": len(tasks),
        "enabled": sum(1 for task in tasks if task["enabled"]),
        "next_run": min(next_runs) if next_runs else "未设置",
    }
    return render_template("index.html", tasks=tasks, stats=stats)


@app.route("/config")
def config_page():
    """Compatibility route for older bookmarks."""
    tasks = list_tasks()
    if tasks:
        return redirect(url_for("edit_task", task_id=tasks[0]["id"]))
    return redirect(url_for("new_task"))


@app.route("/tasks/new", methods=["GET", "POST"])
def new_task():
    """Create a task."""
    if request.method == "POST":
        task_id = create_task(_task_data_from_form(request.form))
        reschedule_jobs()
        flash("任务已创建", "success")
        return redirect(url_for("edit_task", task_id=task_id))

    task = dict(TASK_DEFAULTS)
    task["id"] = None
    task["enabled"] = 1
    return render_template("config.html", task=task, mode="new")


@app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id):
    """Edit a task."""
    task = get_task(task_id)
    if not task:
        flash("任务不存在", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        update_task(task_id, _task_data_from_form(request.form))
        reschedule_jobs()
        flash("任务已保存", "success")
        return redirect(url_for("index"))

    return render_template("config.html", task=task, mode="edit")


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
def delete_task_route(task_id):
    """Delete a task."""
    task = get_task(task_id)
    if not task:
        flash("任务不存在", "error")
    else:
        delete_task(task_id)
        reschedule_jobs()
        flash(f"已删除任务：{task.get('name', task_id)}", "success")
    return redirect(url_for("index"))


@app.route("/tasks/<int:task_id>/send-now", methods=["POST"])
def send_now(task_id):
    """Send one task immediately."""
    success, detail = send_weather_job(task_id)
    if success:
        flash(f"邮件已发送：{detail}", "success")
    else:
        flash(f"发送失败：{detail}", "error")
    return redirect(url_for("index"))


@app.route("/send-now", methods=["POST"])
def legacy_send_now():
    """Compatibility route for the old single-task action."""
    tasks = list_tasks()
    if not tasks:
        flash("还没有可发送的任务", "error")
        return redirect(url_for("index"))
    return send_now(tasks[0]["id"])


def _task_data_from_form(form):
    return {
        "name": form.get("name", ""),
        "enabled": "1" if form.get("enabled") == "1" else "0",
        "smtp_server": form.get("smtp_server", ""),
        "smtp_port": form.get("smtp_port", "465"),
        "smtp_use_ssl": form.get("smtp_use_ssl", "true"),
        "smtp_username": form.get("smtp_username", ""),
        "smtp_password": form.get("smtp_password", ""),
        "smtp_from": form.get("smtp_from", ""),
        "smtp_from_name": form.get("smtp_from_name", "天气助手"),
        "email_to": form.get("email_to", ""),
        "subject_prefix": form.get("subject_prefix", "[天气日报]"),
        "send_hour": form.get("send_hour", "8"),
        "send_minute": form.get("send_minute", "0"),
        "city": form.get("city", "Wuxi"),
        "city_display_name": form.get("city_display_name", "无锡"),
    }


def _format_next_run(job):
    if not job or not job.next_run_time:
        return "未设置"
    return job.next_run_time.astimezone(TZ).strftime("%Y-%m-%d %H:%M")


# ── Startup ───────────────────────────────────────────────

def main():
    log.info("weather-email service starting")
    init_db()
    reschedule_jobs()
    scheduler.start()
    log.info("Web UI: http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()
