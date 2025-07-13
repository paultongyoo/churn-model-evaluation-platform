setup:
	pipenv install --dev
	pre-commit install

quality:
	pipenv run pre-commit run --all-files
