#!/bin/bash

terraform destroy --var-file=vars/stg.tfvars --auto-approve
