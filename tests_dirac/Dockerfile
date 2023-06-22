FROM ghcr.io/xenon-middleware/diracclient:8.0.18

RUN pip install poetry==1.5.1

# Configuring poetry
RUN poetry config virtualenvs.create false

WORKDIR /workspace

# Copying requirements of a project
COPY pyproject.toml poetry.lock ./

# Installing requirements
RUN poetry install --no-root --no-interaction --no-ansi
