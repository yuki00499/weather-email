#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手动触发一次天气邮件发送，执行完即退出"""
import importlib.util

spec = importlib.util.spec_from_file_location(
    "send_weather_email", "/app/send-weather-email.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.job()
print("完成。")