"""This script updates the Prefect deployment configuration to use a Docker container"""

import sys

import yaml

if len(sys.argv) != 2:
    print("Usage: python update_prefect_yaml.py <IMAGE_URI>")
    sys.exit(1)

image_uri = sys.argv[1]

with open("prefect.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)

for deployment in config.get("deployments", []):
    deployment["infrastructure"] = {
        "type": "docker-container",
        "image": image_uri,
        "stream_output": True,
    }

with open("prefect.yaml", "w", encoding="utf-8") as f:
    yaml.dump(config, f, sort_keys=False)
