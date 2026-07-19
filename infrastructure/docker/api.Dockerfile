FROM python:3.11.9-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/home/streamml/.local/bin:${PATH}"

WORKDIR /app

RUN groupadd --system streamml \
    && useradd --system --gid streamml --home-dir /home/streamml --create-home streamml

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements.txt

COPY apps/__init__.py /app/apps/__init__.py
COPY apps/api /app/apps/api
COPY src /app/src

RUN mkdir -p /app/runtime && chown -R streamml:streamml /app /home/streamml
USER streamml

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
