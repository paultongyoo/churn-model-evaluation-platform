setup:
	pipenv install --dev
	pre-commit install

test:
	pipenv run pytest

quality:
	pipenv run pre-commit run --all-files
