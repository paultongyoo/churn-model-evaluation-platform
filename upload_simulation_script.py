"""
This script uploads CSV files from a local folder to an AWS S3 bucket,
excluding a specific file, and waits for 30 seconds between uploads."""

import os
import time

import boto3

# AWS S3 configuration
BUCKET_NAME = "mlops-churn-pipeline"  # Change this to your 'project_id' in stg.tfvars
S3_PREFIX = "data/input/"
LOCAL_FOLDER = "data"
EXCLUDED_FILE = "customer_churn_0.csv"

# Initialize S3 client
s3 = boto3.client("s3")

# Upload files with delay
for filename in os.listdir(LOCAL_FOLDER):
    if filename.endswith(".csv") and filename != EXCLUDED_FILE:
        local_path = os.path.join(LOCAL_FOLDER, filename)
        s3_key = f"{S3_PREFIX}{filename}"  # pylint: disable=invalid-name

        try:
            s3.upload_file(local_path, BUCKET_NAME, s3_key)
            print(f"✅ Uploaded {filename} to s3://{BUCKET_NAME}/{s3_key}")
        except Exception as e:  # pylint: disable=broad-except
            print(f"❌ Failed to upload {filename}: {e}")

        print("⏳ Waiting 30 seconds before next upload...")
        time.sleep(30)
