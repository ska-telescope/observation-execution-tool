# Use bash shell with pipefail option enabled so that the return status of a
# piped command is the value of the last (rightmost) commnand to exit with a
# non-zero status. This lets us pipe output into tee but still exit on test
# failures.
SHELL = /bin/bash
.SHELLFLAGS = -o pipefail -c

TEST_ARTIFACTS = pytest.stdout report.xml report.json cucumber.json pytest-logs.txt coverage.xml htmlcov

all: test

install:
	pip3 install -r test_requirements.txt --use-feature=2020-resolver

# create the build directory
# execute the python tests
# copy TEST_ARTIFACTS into build directory
# exit with same exit code as test run
test: install
	mkdir -p build && \
	find . -name "*.pyc" -type f -delete && \
	PYTHONPATH=/app:/app/testing:/app/testing/post-deployment pytest $(if $(findstring all,$(MARK)),, -m $(MARK)) --disable-pytest-warnings --cov=oet --cov-report=xml:coverage.xml --cov-report=html:htmlcov | tee pytest.stdout; \
	status=$$?; \
	$(foreach artfct,$(TEST_ARTIFACTS),mv -f $(artfct) build/;) \
	exit $$status

lint:
	python3 -m pip install pylint2junit; \
	mkdir -p /build/reports; \
	cd /app && ./code-analysis.sh | tee /build/code_analysis.stdout; \
	cd /app && pylint --output-format=pylint2junit.JunitReporter oet tests/oet > /build/reports/linting.xml; \
	sed -i 's/UTF-8" ?>/UTF-8" ?><testsuites>/' /build/reports/linting.xml; \
	echo "</testsuites>" >> /build/reports/linting.xml; \

.PHONY: all test install
