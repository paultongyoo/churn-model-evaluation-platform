#!/bin/bash

# Exit on any error
set -e

# Parse named parameters
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --project-id) PROJECT_ID="$2"; shift ;;
        --env-file) ENV_FILE="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Validate input
if [[ -z "$PROJECT_ID" ]]; then
    echo "Error: --project-id is required"
    exit 1
fi

if [[ -z "$ENV_FILE" ]]; then
    echo "Error: --env-file is required"
    exit 1
fi

# Create the env file if it doesn't exist
touch "$ENV_FILE"

# Check if PROJECT_ID is already set
if grep -q '^PROJECT_ID=' "$ENV_FILE"; then
    # Replace existing line
    sed -i.bak "s/^PROJECT_ID=.*/PROJECT_ID=${PROJECT_ID}/" "$ENV_FILE"
else
    # Append new line
    echo "PROJECT_ID=${PROJECT_ID}" >> "$ENV_FILE"
fi

echo "✅ PROJECT_ID set to '$PROJECT_ID' in $ENV_FILE"
