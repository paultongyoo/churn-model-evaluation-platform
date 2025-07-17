# Use official Prefect image as the base
FROM prefecthq/prefect:3.4.8-python3.10

RUN pip install -U pip
RUN pip install pipenv

# Set working directory in container
WORKDIR /opt/prefect/orchestration

COPY [ "Pipfile", "Pipfile.lock", "./" ]

# Copy your flow code into the container
# Ensure this is done _before_ installing dependencies
# to include local modules (e.g. 'modeling')
COPY . /opt/prefect/orchestration

RUN pipenv install --system --deploy --verbose

# Prefect version label
LABEL io.prefect.version=3.4.8
