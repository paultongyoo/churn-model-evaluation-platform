# Use official Prefect image as the base
FROM prefecthq/prefect:3.4.8-python3.10

RUN pip install -U pip
RUN pip install pipenv

# Set working directory in container
WORKDIR /opt/prefect/orchestration

COPY [ "Pipfile", "Pipfile.lock", "./" ]

RUN pipenv install --system --deploy --verbose

# Copy your flow code into the container
COPY . /opt/prefect/orchestration

# Prefect version label
LABEL io.prefect.version=3.4.8
