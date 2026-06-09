# -*- coding: utf-8 -*-
"""气温图表生成模块 - 使用 matplotlib 生成折线图 + 多日趋势柱状图"""

import base64
import io
import logging
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # 非交互后端，无需 GUI

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.ticker as mticker
import numpy as np

log = logging.getLogger(__name__)

# ── 中文字体配置 ──────────────────────────────────────────
_FONT_CANDIDATES = [
    "Noto Sans CJK SC",
    "Noto Sans SC",
    "WenQuanYi Micro Hei",
    "SimHei",
    "Microsoft YaHei",
]

def _setup_chinese_font():
    """配置 matplotlib 中文字体"""
    available = {f.name for f in fm.fontManager.ttflist}
    for font_name in _FONT_CANDIDATES:
        if font_name in available:
            matplotlib.rcParams["font.sans-serif"] = [font_name, "DejaVu Sans"]
            matplotlib.rcParams["axes.unicode_minus"] = False
            log.info("Using font: %s", font_name)
            return font_name
    # fallback
    matplotlib.rcParams["font.sans-serif"] = ["DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    log.warning("No Chinese font found, charts may show tofu boxes")
    return None

_FONT_NAME = _setup_chinese_font()

WEEKDAY_CN = {
    "Monday": "周一", "Tuesday": "周二", "Wednesday": "周三",
    "Thursday": "周四", "Friday": "周五", "Saturday": "周六", "Sunday": "周日",
}

# 图表配色 — 与邮件主题 #4facfe / #00f2fe 协调
COLOR_LINE = "#4facfe"          # 折线
COLOR_FILL = "#4facfe33"         # 折线下方半透明填充
COLOR_MAX = "#ff6b6b"           # 最高温
COLOR_MIN = "#4facfe"           # 最低温
COLOR_GRID = "#e8e8e8"
COLOR_BG = "#fafbfc"


def format_date_label(date_str):
    """将 '2026-06-09' 转为 '6月9日 周二'"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        wd = WEEKDAY_CN.get(dt.strftime("%A"), dt.strftime("%A"))
        return f"{dt.month}月{dt.day}日 {wd}"
    except (ValueError, TypeError):
        return date_str


def build_temperature_chart(data):
    """
    生成气温趋势图表（PNG base64）

    参数:
        data: wttr.in JSON (format=j1) 完整响应

    返回:
        base64 编码的 PNG 图片字符串；数据不足时返回 None
    """
    weather_days = data.get("weather", [])
    if not weather_days:
        log.warning("No weather data available for chart")
        return None

    # ── 解析今日逐小时数据 ──
    today = weather_days[0]
    hourly = today.get("hourly", [])
    hours = []
    temps = []
    for h in hourly:
        try:
            hour_val = int(h.get("time", 0)) // 100
            temp_val = float(h.get("tempC", 0))
            hours.append(hour_val)
            temps.append(temp_val)
        except (ValueError, TypeError):
            continue

    # ── 解析多日最高/最低 ──
    day_labels = []
    max_temps = []
    min_temps = []
    for day in weather_days:
        try:
            label = format_date_label(day.get("date", ""))
            mx = float(day.get("maxtempC", 0))
            mn = float(day.get("mintempC", 0))
            day_labels.append(label)
            max_temps.append(mx)
            min_temps.append(mn)
        except (ValueError, TypeError):
            continue

    has_hourly = len(hours) >= 2
    has_multi_day = len(day_labels) >= 2

    if not has_hourly and not has_multi_day:
        log.warning("Not enough data for chart")
        return None

    # ── 创建图表 ──
    nrows = 0
    row_idx = 0
    if has_hourly:
        nrows += 1
    if has_multi_day:
        nrows += 1

    fig, axes = plt.subplots(
        nrows=nrows, ncols=1,
        figsize=(7, 2.8 * nrows),
        dpi=100,
        facecolor=COLOR_BG,
    )
    if nrows == 1:
        axes = [axes]

    if has_hourly:
        ax = axes[row_idx]
        row_idx += 1

        ax.fill_between(hours, temps, alpha=0.15, color=COLOR_FILL)
        ax.plot(hours, temps, color=COLOR_LINE, linewidth=2.5, marker="o",
                markersize=8, markerfacecolor="white", markeredgewidth=2,
                markeredgecolor=COLOR_LINE, zorder=5)

        for h, t in zip(hours, temps):
            ax.annotate(
                f"{t:.0f}°", (h, t),
                textcoords="offset points", xytext=(0, 14),
                fontsize=9, ha="center", color="#444",
                fontweight="bold",
            )

        ax.set_title("今日逐小时气温变化", fontsize=13, fontweight="bold",
                     color="#333", pad=10)
        ax.set_ylabel("温度 (°C)", fontsize=9, color="#888")
        ax.set_ylim(min(temps) - 3, max(temps) + 3)
        ax.set_xticks(hours)
        ax.set_xticklabels([f"{h:02d}:00" for h in hours], fontsize=8, color="#888")
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%d°"))
        ax.tick_params(axis="y", labelsize=8, colors="#888")
        ax.set_xlim(hours[0] - 0.8, hours[-1] + 0.8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(COLOR_GRID)
        ax.spines["bottom"].set_color(COLOR_GRID)
        ax.grid(axis="y", color=COLOR_GRID, linewidth=0.6, alpha=0.8)
        ax.set_facecolor("white")

    if has_multi_day:
        ax = axes[row_idx]

        x = np.arange(len(day_labels))

        # 最高温折线
        ax.plot(x, max_temps, color=COLOR_MAX, linewidth=2.5, marker="o",
                markersize=8, markerfacecolor="white", markeredgewidth=2,
                markeredgecolor=COLOR_MAX, label="最高温", zorder=5)
        # 最低温折线
        ax.plot(x, min_temps, color=COLOR_MIN, linewidth=2.5, marker="o",
                markersize=8, markerfacecolor="white", markeredgewidth=2,
                markeredgecolor=COLOR_MIN, label="最低温", zorder=4)

        # 最高温数据标签（上方）
        for xi, t in zip(x, max_temps):
            ax.annotate(
                f"{t:.0f}°", (xi, t),
                textcoords="offset points", xytext=(0, 12),
                fontsize=8, ha="center", color="#e55",
                fontweight="bold",
            )
        # 最低温数据标签（下方）
        for xi, t in zip(x, min_temps):
            ax.annotate(
                f"{t:.0f}°", (xi, t),
                textcoords="offset points", xytext=(0, -16),
                fontsize=8, ha="center", color="#4a9",
                fontweight="bold",
            )

        ax.set_title("未来几日气温趋势", fontsize=13, fontweight="bold",
                     color="#333", pad=10)
        ax.set_ylabel("温度 (°C)", fontsize=9, color="#888")
        ax.set_xticks(x)
        ax.set_xticklabels(day_labels, fontsize=8, color="#666")
        ax.legend(loc="upper right", fontsize=8, framealpha=0.9,
                  edgecolor=COLOR_GRID)

        all_temps = max_temps + min_temps
        y_pad = 4 if all_temps else 5
        ax.set_ylim(min(all_temps) - y_pad, max(all_temps) + y_pad)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%d°"))
        ax.tick_params(axis="y", labelsize=8, colors="#888")
        ax.set_xlim(x[0] - 0.5, x[-1] + 0.5)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(COLOR_GRID)
        ax.spines["bottom"].set_color(COLOR_GRID)
        ax.grid(axis="y", color=COLOR_GRID, linewidth=0.6, alpha=0.8)
        ax.set_facecolor("white")


    plt.tight_layout(pad=2.0)

    # ── 输出为 base64 ──
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")
    return img_base64
