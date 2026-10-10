FROM python:3.11.9-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config default-libmysqlclient-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt scripts/check_installed.py ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip check \
    && python check_installed.py requirements.txt
# RUN pip install --no-cache-dir -r requirements.txt \
#     && pip check \
#     && python check_installed.py requirements.txt
COPY . .
CMD ["gunicorn", "onecare_chat.wsgi:application", "--bind", "0.0.0.0:8000"]