# Use official Prefect image as the base
FROM prefecthq/prefect:3.4.8-python3.9

# Set working directory in container
WORKDIR /opt/prefect/flows

# Copy your flow code into the container
COPY . /opt/prefect/flows

# (Optional) Install any extra dependencies here
# RUN pip install boto3 xgboost pandas

# Prefect version label
LABEL io.prefect.version=3.4.8
