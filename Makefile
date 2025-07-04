.PHONY: clean build test-upload upload install-tools test help

help:
	@echo "Available commands:"
	@echo "  make install-tools  - Install required packaging tools"
	@echo "  make clean         - Clean build artifacts"
	@echo "  make build         - Build distribution packages"
	@echo "  make test          - Run tests (if available)"
	@echo "  make test-upload   - Upload to Test PyPI"
	@echo "  make upload        - Upload to Production PyPI"
	@echo "  make release       - Full release process (clean, build, upload)"

install-tools:
	pip install --upgrade pip setuptools wheel twine build

clean:
	rm -rf build/ dist/ src/*.egg-info/ .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build
	twine check dist/*

test:
	@echo "No tests configured yet"
	# pytest tests/  # Uncomment when you add tests

test-upload: build
	@echo "Uploading to Test PyPI..."
	@echo "Username: __token__"
	@echo "Password: Use your Test PyPI token"
	twine upload --repository testpypi dist/* --verbose

upload: build
	@echo "Uploading to Production PyPI..."
	@echo "Username: __token__"
	@echo "Password: Use your Production PyPI token"
	twine upload dist/* --verbose

release: clean build
	@echo "Ready to release version $$(python -c 'import src.migs; print(src.migs.__version__)')"
	@echo "This will upload to Production PyPI. Continue? [y/N]"
	@read ans && [ $${ans:-N} = y ] && make upload || echo "Release cancelled."

# Development commands
dev-install:
	pip install -e .

dev-uninstall:
	pip uninstall -y migs