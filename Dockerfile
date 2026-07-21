FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system workbench \
    && useradd --system --gid workbench --home-dir /app workbench

COPY pyproject.toml README.md LICENSE ./
COPY app ./app
RUN python -m pip install --upgrade pip \
    && python -m pip install .

COPY templates ./templates
COPY static ./static
RUN mkdir -p /app/data \
    && chown -R workbench:workbench /app

USER workbench

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
