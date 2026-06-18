FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（matplotlib 图形渲染 + 中文字体）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6-dev \
    libpng-dev \
    pkg-config \
    fonts-wqy-microhei \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制应用代码
COPY app/ ./app/

# 创建数据目录
RUN mkdir -p /app/data

# 设置时区
ENV TZ=Asia/Hong_Kong
RUN ln -snf /usr/share/zoneinfo/ /etc/localtime && echo  > /etc/timezone

# 暴露 Web UI 端口
EXPOSE 5000

CMD ["python", "-m", "app.main"]
