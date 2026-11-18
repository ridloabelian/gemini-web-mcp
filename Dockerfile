FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DISPLAY=:99 \
    GEMINI_PROFILE_DIR=/data/profile \
    GEMINI_HEADLESS=false \
    GEMINI_BROWSER_CHANNEL=

# Instal Xvfb + Fluxbox + x11vnc + noVNC agar browser dapat berjalan headed di layar virtual
# (menghindari deteksi headless Google) sekaligus menyediakan portal login web pertama kali.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    fluxbox \
    fonts-liberation \
    fonts-noto-color-emoji \
    novnc \
    tini \
    websockify \
    x11vnc \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev
RUN uv run patchright install --with-deps chromium

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && mkdir -p /data/profile

EXPOSE 8765 6080

ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
