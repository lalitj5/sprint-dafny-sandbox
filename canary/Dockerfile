FROM python:3.13-slim

RUN useradd --create-home --uid 1001 canary \
 && mkdir -p /var/log/canary \
 && chown canary:canary /var/log/canary

COPY --chown=canary:canary canary.py /app/canary.py

USER canary
EXPOSE 8888
CMD ["python", "-u", "/app/canary.py"]
