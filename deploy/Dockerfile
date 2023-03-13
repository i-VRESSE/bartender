FROM python:3.10-slim-buster

RUN pip install poetry==1.4.0

# Configuring poetry
RUN poetry config virtualenvs.create false

WORKDIR /app/src

# Copying requirements of a project
COPY pyproject.toml poetry.lock ./

# Installing requirements
RUN poetry install --without=dev --no-root --no-interaction --no-ansi

# Copying actuall application
COPY . .
RUN poetry install --without=dev --no-interaction --no-ansi

CMD ["/usr/local/bin/bartender", "serve"]
