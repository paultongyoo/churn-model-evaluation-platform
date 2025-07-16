setup:
	pipenv install --dev
	pre-commit install

test:
	pipenv run pytest --import-mode=importlib

quality:
	pipenv run pre-commit run --all-files

commit: quality test
	@echo "Staging all changes..."
	git add .

	@echo "Enter commit message: " && read msg && \
	if [ -n "$$msg" ]; then \
		git commit -m "$$msg"; \
	else \
		echo "Aborted: No commit message entered."; \
	fi
