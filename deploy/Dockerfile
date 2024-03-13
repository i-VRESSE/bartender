FROM python:3.10-slim-buster

# Install healthcheck dependency
RUN apt update && apt install -y curl unzip

RUN pip install poetry==1.7.0

# Configuring poetry
RUN poetry config virtualenvs.create false

WORKDIR /app/src

# Copying requirements of a project
COPY pyproject.toml poetry.lock ./

# Installing requirements
RUN poetry install --without=dev --no-root --no-interaction --no-ansi

# Copying actual application
COPY . .
RUN poetry install --without=dev --no-interaction --no-ansi

ENV BARTENDER_HOST=0.0.0.0
ENV BARTENDER_PORT=8000

# Mounting config.yaml and public_key.pem should be done when running the container

CMD ["/usr/local/bin/bartender", "serve"]

HEALTHCHECK --interval=5m --timeout=3s CMD curl -f http://${BARTENDER_HOST}:${BARTENDER_PORT}/api/health || exit 1
