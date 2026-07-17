FROM python:3.11-alpine

RUN apk add --no-cache ffmpeg
WORKDIR /app
COPY apps/media /app/apps/media
RUN chmod 0555 /app/apps/media/generate_fallback.sh \
    && addgroup -S streamml \
    && adduser -S -G streamml streamml

USER streamml
CMD ["python", "-m", "apps.media.restream_worker"]
