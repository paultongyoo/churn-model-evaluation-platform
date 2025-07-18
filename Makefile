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
	echo "MLflow, Prefect, and Evidently UI URLs"; \
	echo "--------------------------"; \
	echo "(May need to wait for ECS Tasks to activate)"; \
	echo ""; \
	export $$(grep -E '^MLFLOW_TRACKING_URI=|^PREFECT_API_URL=|^EVIDENTLY_UI_URL=' .env | xargs); \
	PREFECT_UI_URL=$$(echo $$PREFECT_API_URL | sed 's:/api$$::'); \
	echo ""; \
	echo "MLflow UI: $$MLFLOW_TRACKING_URI"; \
	echo "Prefect UI: $$PREFECT_UI_URL"; \
	echo "Evidently UI: $$EVIDENTLY_UI_URL"; \
	echo ""; \

destroy:
	cd infrastructure && \
	terraform destroy -var-file=vars/stg.tfvars --auto-approve
