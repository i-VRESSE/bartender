FROM ghcr.io/xenon-middleware/diracclient:8.0.18

COPY ../pyproject.toml ../poetry.lock ./

# Trick poetry to install deps in conda base environment, by renaming it from base to diracos.
RUN export CONDA_DEFAULT_ENV=diracos && \
    pip install poetry && \
    poetry install --no-root
