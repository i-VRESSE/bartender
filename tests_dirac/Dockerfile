FROM ghcr.io/xenon-middleware/diracclient:8.0.49

RUN pip install --upgrade pip wheel setuptools && \
    pip install poetry==1.7.0

# Configuring poetry
RUN poetry config virtualenvs.create false

WORKDIR /workspace

# Copying requirements of a project
COPY pyproject.toml poetry.lock ./

# Installing requirements
RUN poetry install --no-root --no-interaction --no-ansi --with dev

# Workaround `ImportWarning: _SixMetaPathImporter.find_spec() not found; falling back to find_module()` error
RUN /home/diracuser/diracos/bin/micromamba install -y m2crypto==0.041.0
