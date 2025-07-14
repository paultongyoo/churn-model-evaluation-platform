"""This script updates the Prefect deployment configuration to use a Docker container"""

import sys

import yaml

if len(sys.argv) != 2:
    print("Usage: python update_prefect_yaml.py <IMAGE_NAME> <IMAGE_TAG>")
    sys.exit(1)

image_name = sys.argv[1]
image_tag = sys.argv[2]

with open("prefect.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# Update image in the build section
if "build" in config:
    for step in config["build"]:
        if isinstance(step, dict):
            for key, val in step.items():
                if key == "prefect_docker.deployments.steps.build_docker_image":
                    val["image_name"] = image_name
                    val["tag"] = image_tag

with open("prefect.yaml", "w", encoding="utf-8") as f:
    yaml.dump(config, f, sort_keys=False)
