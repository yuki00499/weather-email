# -*- coding: utf-8 -*-
"""SQLite 配置持久化模块"""

import os
import sqlite3
import logging
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
    """初始化数据库，首次运行时尝试从 .env 迁移配置"""
    conn = _get_conn()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)"
    )
    conn.commit()

    existing = {row["key"] for row in conn.execute("SELECT key FROM config")}

    # 插入缺少的默认值
    for key, default_val in DEFAULTS.items():
        if key not in existing:
            # 尝试从环境变量读取旧配置
            env_key = ENV_MAP.get(key)
            env_val = os.getenv(env_key, "") if env_key else ""
            value = env_val if env_val else default_val
            conn.execute("INSERT INTO config (key, value) VALUES (?, ?)", (key, value))
            log.info("config init: %s = %s (source: %s)", key,
                     _mask_value(key, value),
                     "env" if env_val else "default")

    conn.commit()
    conn.close()


def get_config(key):
    """获取单个配置值"""
    conn = _get_conn()
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row:
        return row["value"]
    return DEFAULTS.get(key, "")


def get_all_configs():
    """获取所有配置（字典）"""
    conn = _get_conn()
    rows = conn.execute("SELECT key, value FROM config").fetchall()
    conn.close()
    result = dict(DEFAULTS)
    for row in rows:
        result[row["key"]] = row["value"]
    return result


def set_config(key, value):
    """设置单个配置值"""
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


def save_configs(data: dict):
    """批量保存配置"""
    conn = _get_conn()
    for key, value in data.items():
        if key in DEFAULTS:
            conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, str(value)),
            )
    conn.commit()
    conn.close()


def _mask_value(key, value):
    """对敏感字段脱敏"""
    if key in ("smtp_password",):
        return "***" if value else "(empty)"
    return value
