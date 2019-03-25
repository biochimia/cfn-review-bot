all:

clean: clean-dist

clean-deps:
	@rm -rf .venv-dist

clean-dist:
	@rm -rf build cfn_review_bot.egg-info dist
	@rm -f cfn_review_bot/package-version.json

deps-dist: .venv-dist/.env-ready

.venv-dist/.env-ready:
	@python -m venv .venv-dist
	@.venv-dist/bin/pip install twine
	@touch .venv-dist/.env-ready

dist: clean-dist deps-dist
	@python setup.py sdist bdist_wheel
	@rm -f cfn_review_bot/package-version.json

release: dist
	@.venv-dist/bin/pip install twine
	@.venv-dist/bin/twine upload dist/*

test:
	@echo 'Ha!'

.PHONY: all clean clean-deps clean-dist deps-dist dist release test
