# AGENTS.md — weather-email 项目指南

## 项目概述

自动获取天气数据并通过邮件发送天气日报的 Python 应用。
部署为 Docker 容器，提供 Web UI 配置页面，支持定时发送和手动触发。

## 技术栈

- **Python 3.11** + Flask (Web UI) + APScheduler (定时任务)
- **数据源**: wttr.in JSON API (ormat=j1)
- **邮件**: SMTP (QQ邮箱等)，SSL/TLS
- **存储**: SQLite (data/weather-email.db)，保存SMTP配置和城市设置
- **部署**: Docker + docker-compose

## 目录结构

`
├── Dockerfile              # 构建镜像
├── docker-compose.yml      # 端口8080:5000，volumes持久化 /app/data
├── requirements.txt        # requests, pytz, flask, apscheduler
├── AGENTS.md               # 本文件
├── app/
│   ├── main.py             # 入口：Flask路由 + 定时任务调度
│   ├── weather.py          # 天气获取 + 天气描述中英翻译 + 生活建议
│   ├── email_service.py    # HTML邮件模板构建 + SMTP发送
│   ├── models.py           # SQLite配置CRUD（含.env迁移逻辑）
│   ├── templates/          # Jinja2：index.html(仪表盘), config.html(配置页), base.html
│   └── static/style.css
├── send-weather-email.py   # [旧版] 独立脚本，Docker未使用，仅trigger.py引用
└── trigger.py              # 手动触发脚本（导入send-weather-email.py执行job）
`

## 核心数据流

1. etch_weather(city) 调用 https://wttr.in/{city}?format=j1&lang=zh
2. wttr.in JSON API **始终返回英文**描述（lang=zh 不影响 JSON），通过 WEATHER_DESC_CN 字典转为中文
3. uild_html(data, config) 构建完整 HTML，含当前天气、逐小时预报、生活建议
4. send_email(config, html) 通过 SMTP 发送

`
wttr.in API -> fetch_weather() -> translate_desc() -> build_html() -> send_email()
                   (weather.py)    (weather.py)     (email_service.py)
`

## 关键模块说明

### app/weather.py
- WEATHER_ICONS: weatherCode -> emoji 映射
- WIND_CN: 风向英文缩写 -> 中文（如NSEW转北南东西）
- WEATHER_DESC_CN: 英文天气描述 -> 中文（**注意**: API返回值带尾部空格，translate_desc 已做 strip 处理）
- 	ranslate_desc(desc): 先 strip()，再精确匹配，最后大小写不敏感 fallback
- uild_suggestion(temp_c, weather_code): 根据温度和天气码生成中文生活建议

### app/email_service.py
- uild_html(data, config): 内嵌CSS的独立HTML邮件（兼容邮件客户端），从config读取城市名和发送时间
- 邮件标注 lang=zh-CN，字体优先 Microsoft YaHei / PingFang SC
- send_email(config, html): SMTP_SSL 或 STARTTLS，从config读取全部SMTP参数

### app/models.py
- 默认配置 DEFAULTS 字典，城市默认值 city=Wuxi, city_display_name=无锡
- init_db() 首次运行自动从 .env 环境变量迁移配置到 SQLite
- 敏感字段 smtp_password 日志输出时脱敏

### app/main.py
- Flask 路由: / (仪表盘), /config (配置页), /send-now (手动发送POST)
- APScheduler 每天定时触发 send_weather_job()
- 配置修改后自动 
eschedule_job() 更新定时任务

## Docker 部署

`ash
docker compose up -d --build    # 构建并启动
# 访问 http://<IP>:8080 配置SMTP后即可使用
`

- 端口映射: 8080:5000
- 数据持久化: volume weather-email-data -> /app/data
- 时区: Asia/Hong_Kong

## 编码注意事项

- 所有 .py 文件头标注 # -*- coding: utf-8 -*-
- 中文字符串在字典和模板中直接使用
- Windows 终端输出中文需设置 sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
- 天气描述翻译统一为两字中文（如晴朗、阴天、大雾、灰霾）
