FROM ghcr.io/xenon-middleware/diracclient:8.0.18

RUN pip install poetry==1.8.2 && \
    pip install --upgrade pip wheel setuptools

# Configuring poetry
RUN poetry config virtualenvs.create false

WORKDIR /workspace

# Copying requirements of a project
COPY pyproject.toml poetry.lock ./

# Installing requirements
RUN poetry install --no-root --no-interaction --no-ansi && pip3 install pyOpenSSL --upgrade
