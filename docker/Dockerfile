FROM python:3.13-slim

RUN useradd --create-home --uid 1000 agent \
 && mkdir -p /work /opt/fixtures \
 && chown agent:agent /work /opt/fixtures

# Staging area, NOT /work -- the tmpfs mounted at /work at runtime would hide these.
COPY --chown=agent:agent fixtures/script.py    /opt/fixtures/script.py
COPY --chown=agent:agent fixtures/secrets.env  /opt/fixtures/secrets.env

WORKDIR /work
USER agent

CMD ["sleep", "infinity"]