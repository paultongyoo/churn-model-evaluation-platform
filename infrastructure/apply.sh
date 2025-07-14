#!/bin/sh

terraform apply --var-file=vars/stg.tfvars --auto-approve
