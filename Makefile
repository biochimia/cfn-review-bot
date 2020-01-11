all: lint test dist

.venv-%/.env-ready:
	$(eval _VENV=$(patsubst .venv-%/.env-ready,%,$@))
	@python -m venv .venv-$(_VENV)
	@.venv-$(_VENV)/bin/pip install -r requirements/$(_VENV).txt
	@touch $@

clean: clean-dist

clean-all: clean-test clean

clean-deps:
	@rm -rf .venv-dist

clean-dist:
	@rm -rf build cfn_review_bot.egg-info dist
	@rm -f cfn_review_bot/package-version.json

clean-test:
	@rm -rf .venv-test

deps-dist: .venv-dist/.env-ready

deps-test: .venv-test/.env-ready

dist: clean-dist deps-dist
	@python setup.py sdist bdist_wheel
	@rm -f cfn_review_bot/package-version.json

lint: deps-test
	@.venv-test/bin/flake8 cfn_review_bot --max-line-length=100 --statistics

release: clean-all test dist
	@.venv-dist/bin/pip install twine
	@.venv-dist/bin/twine upload dist/*

test: deps-test
	@.venv-test/bin/python -m unittest -v

.PHONY: all clean clean-all clean-deps clean-dist clean-test deps-dist deps-test dist lint release test
