# -*- coding: utf-8 -*-
"""SQLite persistence for weather-email configuration and tasks."""

import logging
import os
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "weather-email.db"

DEFAULTS = {
    "smtp_server": "smtp.qq.com",
    "smtp_port": "465",
    "smtp_use_ssl": "true",
    "smtp_username": "",
    "smtp_password": "",
    "smtp_from": "",
    "smtp_from_name": "天气助手",
    "email_to": "",
    "subject_prefix": "[天气日报]",
    "send_hour": "8",
    "send_minute": "0",
    "city": "Wuxi",
    "city_display_name": "无锡",
}

TASK_DEFAULTS = {
    "name": "默认天气日报",
    "enabled": "1",
    **DEFAULTS,
}

TASK_FIELDS = (
    "name",
    "enabled",
    "smtp_server",
    "smtp_port",
    "smtp_use_ssl",
    "smtp_username",
    "smtp_password",
    "smtp_from",
    "smtp_from_name",
    "email_to",
    "subject_prefix",
    "send_hour",
    "send_minute",
    "city",
    "city_display_name",
)

ENV_MAP = {
    "smtp_server": "SMTP_SERVER",
    "smtp_port": "SMTP_PORT",
    "smtp_use_ssl": "SMTP_USE_SSL",
    "smtp_username": "SMTP_USERNAME",
    "smtp_password": "SMTP_PASSWORD",
    "smtp_from": "SMTP_FROM",
    "smtp_from_name": "SMTP_FROM_NAME",
    "email_to": "EMAIL_TO",
    "subject_prefix": "SUBJECT_PREFIX",
    "send_hour": "SEND_HOUR",
    "send_minute": "SEND_MINUTE",
}


def _get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize tables and migrate the old single config to a default task."""
    conn = _get_conn()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            smtp_server TEXT NOT NULL DEFAULT '',
            smtp_port TEXT NOT NULL DEFAULT '465',
            smtp_use_ssl TEXT NOT NULL DEFAULT 'true',
            smtp_username TEXT NOT NULL DEFAULT '',
            smtp_password TEXT NOT NULL DEFAULT '',
            smtp_from TEXT NOT NULL DEFAULT '',
            smtp_from_name TEXT NOT NULL DEFAULT '天气助手',
            email_to TEXT NOT NULL DEFAULT '',
            subject_prefix TEXT NOT NULL DEFAULT '[天气日报]',
            send_hour INTEGER NOT NULL DEFAULT 8,
            send_minute INTEGER NOT NULL DEFAULT 0,
            city TEXT NOT NULL DEFAULT 'Wuxi',
            city_display_name TEXT NOT NULL DEFAULT '无锡',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_legacy_config(conn)
    _migrate_config_to_default_task(conn)
    conn.commit()
    conn.close()


def _ensure_legacy_config(conn):
    existing = {row["key"] for row in conn.execute("SELECT key FROM config")}
    for key, default_val in DEFAULTS.items():
        if key not in existing:
            env_key = ENV_MAP.get(key)
            env_val = os.getenv(env_key, "") if env_key else ""
            value = env_val if env_val else default_val
            conn.execute("INSERT INTO config (key, value) VALUES (?, ?)", (key, value))
            log.info(
                "config init: %s = %s (source: %s)",
                key,
                _mask_value(key, value),
                "env" if env_val else "default",
            )


def _migrate_config_to_default_task(conn):
    count = conn.execute("SELECT COUNT(*) AS count FROM tasks").fetchone()["count"]
    if count:
        return

    config = _get_all_configs_from_conn(conn)
    task = dict(TASK_DEFAULTS)
    task.update(config)
    task["name"] = TASK_DEFAULTS["name"]
    task["enabled"] = "1"
    _insert_task(conn, task)
    log.info("legacy config migrated to default task")


def get_config(key):
    """Get a legacy config value."""
    conn = _get_conn()
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row:
        return row["value"]
    return DEFAULTS.get(key, "")


def get_all_configs():
    """Get all legacy config values."""
    conn = _get_conn()
    result = _get_all_configs_from_conn(conn)
    conn.close()
    return result


def _get_all_configs_from_conn(conn):
    rows = conn.execute("SELECT key, value FROM config").fetchall()
    result = dict(DEFAULTS)
    for row in rows:
        result[row["key"]] = row["value"]
    return result


def set_config(key, value):
    """Set a legacy config value."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


def save_configs(data: dict):
    """Save legacy config values."""
    conn = _get_conn()
    for key, value in data.items():
        if key in DEFAULTS:
            conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, str(value)),
            )
    conn.commit()
    conn.close()


def list_tasks():
    """Return all tasks ordered by creation."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM tasks ORDER BY id ASC").fetchall()
    conn.close()
    return [_row_to_task(row) for row in rows]


def list_enabled_tasks():
    """Return enabled tasks ordered by creation."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE enabled = 1 ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return [_row_to_task(row) for row in rows]


def get_task(task_id):
    """Return one task or None."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return _row_to_task(row) if row else None


def create_task(data):
    """Create a task and return its id."""
    conn = _get_conn()
    task_id = _insert_task(conn, _normalize_task_data(data))
    conn.commit()
    conn.close()
    return task_id


def update_task(task_id, data):
    """Update an existing task."""
    values = _normalize_task_data(data)
    assignments = ", ".join(f"{field} = ?" for field in TASK_FIELDS)
    params = [values[field] for field in TASK_FIELDS]
    params.append(task_id)

    conn = _get_conn()
    conn.execute(
        f"UPDATE tasks SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        params,
    )
    conn.commit()
    conn.close()


def delete_task(task_id):
    """Delete a task."""
    conn = _get_conn()
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def _insert_task(conn, data):
    values = _normalize_task_data(data)
    fields = ", ".join(TASK_FIELDS)
    placeholders = ", ".join("?" for _ in TASK_FIELDS)
    cursor = conn.execute(
        f"INSERT INTO tasks ({fields}) VALUES ({placeholders})",
        [values[field] for field in TASK_FIELDS],
    )
    return cursor.lastrowid


def _normalize_task_data(data):
    normalized = dict(TASK_DEFAULTS)
    normalized.update({key: value for key, value in data.items() if key in TASK_FIELDS})

    normalized["name"] = str(normalized.get("name") or "").strip() or "未命名任务"
    normalized["enabled"] = 1 if str(normalized.get("enabled", "0")).lower() in (
        "1",
        "true",
        "on",
        "yes",
    ) else 0
    normalized["smtp_use_ssl"] = (
        "true"
        if str(normalized.get("smtp_use_ssl", "true")).lower() in ("1", "true", "on", "yes")
        else "false"
    )
    normalized["send_hour"] = _clamp_int(normalized.get("send_hour"), 0, 23, 8)
    normalized["send_minute"] = _clamp_int(normalized.get("send_minute"), 0, 59, 0)

    for key in TASK_FIELDS:
        if key not in ("enabled", "send_hour", "send_minute"):
            normalized[key] = str(normalized.get(key, "")).strip()
    return normalized


def _row_to_task(row):
    task = dict(row)
    task["enabled"] = int(task.get("enabled") or 0)
    task["send_hour"] = int(task.get("send_hour") or 0)
    task["send_minute"] = int(task.get("send_minute") or 0)
    return task


def _clamp_int(value, min_value, max_value, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, number))


def _mask_value(key, value):
    """Mask sensitive values for logs."""
    if key in ("smtp_password",):
        return "***" if value else "(empty)"
    return value
