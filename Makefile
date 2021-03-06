.PHONY: setup-dev
setup-dev:
	@pip install -rrequirements.txt -rrequirements.dev.txt


.PHONY: release
release:
	@rm -rf ./build
	@rm -rf ./dist
	@python setup.py sdist bdist_wheel --universal
	@twine upload dist/*


.PHONY: docs
docs:
	@sphinx-build -M html "./docs" "./docs/_build"


.PHONY: format
format:
	@isort -rc . && black .


.PHONY: test
test:
	@rm -f .coverage*
	@TOX_SKIP_ENV=coverage tox -p 4
