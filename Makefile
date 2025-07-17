setup:
	pipenv install --dev
	pre-commit install

test:
	pipenv run pytest -v --import-mode=importlib

quality:
	pipenv run pre-commit run --all-files

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
	echo "MLflow and Prefect UI URLs"; \
	echo "--------------------------"; \
	echo "(May need to wait for ECS Tasks to activate)"; \
	echo ""; \
	export $$(grep -E '^MLFLOW_TRACKING_URI=|^PREFECT_API_URL=' .env | xargs); \
	PREFECT_UI_URL=$$(echo $$PREFECT_API_URL | sed 's:/api$$::'); \
	echo ""; \
	echo "MLflow UI: $$MLFLOW_TRACKING_URI"; \
	echo "Prefect UI: $$PREFECT_UI_URL"; \
	echo ""; \

destroy:
	cd infrastructure && \
	terraform destroy -var-file=vars/stg.tfvars --auto-approve
