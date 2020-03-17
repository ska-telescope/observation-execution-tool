# Use bash shell with pipefail option enabled so that the return status of a
# piped command is the value of the last (rightmost) commnand to exit with a
# non-zero status. This lets us pipe output into tee but still exit on test
# failures.
SHELL = /bin/bash
.SHELLFLAGS = -o pipefail -c

all: test

# wait for the device to be available before beginning the test
# A temporary volume is mounted at /build when 'make test' is executing.
# The following steps copy across useful output to this volume which can
# then be extracted to form the CI summary for the test procedure.
test:
	cd /app && python setup.py test | tee setup_py_test.stdout
	-cd /app && ./code-analysis.sh | tee code_analysis.stdout
	if [ -d /build ]; then \
		mkdir -p /build/reports; \
		mv /app/setup_py_test.stdout /build; \
		mv /app/code_analysis.stdout /build; \
		mv /app/htmlcov /build; \
		mv /app/coverage.xml /build/reports/code-coverage.xml; \
	fi;
lint:
	python3 -m pip install pylint2junit; \
	mkdir -p /build/reports; \
	cd /app && pylint --output-format=parseable tangogql ska| tee /build/code_analysis.stdout; \
	cd /app && pylint --output-format=pylint2junit.JunitReporter tangogql ska > /build/reports/linting.xml; \
	sed -i 's/UTF-8" ?>/UTF-8" ?><testsuites>/' /build/reports/linting.xml; \
	echo "</testsuites>" >> /build/reports/linting.xml; \

.PHONY: all test
