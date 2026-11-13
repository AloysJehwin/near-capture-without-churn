# Shortcuts. Each target is one Python command; none needs anything but Python 3.10+.
.PHONY: verify rebuild test refresh

verify:
	python3 -m cwc verify

rebuild:
	python3 -m cwc rebuild

test:
	python3 -m unittest discover -s tests

refresh:
	python3 scripts/refresh.py
