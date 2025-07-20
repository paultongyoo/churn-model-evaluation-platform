SHELL := /bin/bash

.PHONY: disable-s3-lambda enable-s3-lambda setup test quality commit plan apply destroy

setup:
	pre-commit install

test:
	pytest -v --import-mode=importlib

quality:
	@ABS_PATH=$$(realpath code/orchestration/modeling) && \
	sed "s|MODELING_PKG_ABS_PATH|$${ABS_PATH}|" .pre-commit-config.template.yaml > .pre-commit-config.yaml && \
	pre-commit run --all-files

commit:
	@echo "Staging all changes..."
	git add .

	@echo "Enter commit message: " && read msg && \
	if [ -n "$$msg" ]; then \
		echo "Committing changes..."; \
		git commit -m "$$msg"; \
		echo "Pulling latest changes from origin..."; \
		git pull --rebase; \
		echo "Pushing to origin..."; \
		git push origin HEAD; \
	else \
		echo "Aborted: No commit message entered."; \
	fi

plan:
	cd infrastructure && \
	terraform plan -var-file=vars/stg.tfvars

apply:
	@echo "Running Terraform apply..."
	cd infrastructure && \
	terraform apply --var-file=vars/stg.tfvars --auto-approve

	@echo ""; \
	echo "🎉 All systems go! 🎉"; \
	echo ""; \
	echo "MLflow, Prefect, and Evidently UI URLs"; \
	echo "--------------------------------------"; \
	echo ""; \
	export $$(grep -E '^MLFLOW_TRACKING_URI=|^PREFECT_API_URL=|^EVIDENTLY_UI_URL=' .env | xargs); \
	PREFECT_UI_URL=$$(echo $$PREFECT_API_URL | sed 's:/api$$::'); \
	echo ""; \
	echo "🧪 MLflow UI: $$MLFLOW_TRACKING_URI"; \
	echo "⚙️ Prefect UI: $$PREFECT_UI_URL"; \
	echo "📈 Evidently UI: $$EVIDENTLY_UI_URL"; \
	echo ""; \

destroy:
	cd infrastructure && \
	terraform destroy -var-file=vars/stg.tfvars --auto-approve

disable-lambda:
	@echo "🛑 Disabling S3-to-Lambda trigger by updating prefix to 'disabled/'..."
	cd infrastructure && \
	terraform apply -var="lambda_filter_prefix=disabled/" -var-file=vars/stg.tfvars -auto-approve

enable-lambda:
	@echo "✅ Enabling S3-to-Lambda trigger by restoring prefix to 'data/input/'..."
	cd infrastructure && \
	terraform apply -var="lambda_filter_prefix=data/input/" -var-file=vars/stg.tfvars -auto-approve

register-model:
	@echo "Registering model in MLflow..."
	cd code/orchestration/modeling && \
	python churn_training.py

process-test-data:
	@echo "Processing test data..."
	bash -c '\
		source .env && \
		cd code/orchestration && \
		python churn_prediction_pipeline.py mlops-churn-pipeline data/input/customer_churn_1.csv \
	'
