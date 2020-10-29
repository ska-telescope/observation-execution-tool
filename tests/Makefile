# Use bash shell with pipefail option enabled so that the return status of a
# piped command is the value of the last (rightmost) commnand to exit with a
# non-zero status. This lets us pipe output into tee but still exit on test
# failures.
SHELL = /bin/bash
.SHELLFLAGS = -o pipefail -c

all: test

# create the build directory
# execute the python tests
# exit with same exit code as test run
test:
	mkdir -p /app/build && \
	tox -e py37 | tee /app/build/pytest.stdout && \
	status=$$?; \
	exit $$status

lint:
	mkdir -p /app/build/reports; \
	cd /app && ./code-analysis.sh | tee build/code_analysis.stdout; \
	cd /app && pylint --output-format=pylint2junit.JunitReporter oet tests/unit > build/reports/linting.xml; \
	sed -i 's/UTF-8" ?>/UTF-8" ?><testsuites>/' build/reports/linting.xml; \
	echo "</testsuites>" >> build/reports/linting.xml; \

.PHONY: all test install lint
