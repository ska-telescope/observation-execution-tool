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
		mv /app/setup_py_test.stdout /build; \
		mv /app/code_analysis.stdout /build; \
		mv /app/htmlcov /build; \
		mv /app/coverage.xml /build; \
	fi;

test-cli:
	[ -f /.dockerenv ] && sudo apt-get update && sudo apt-get -y install --no-install-recommends expect || true
    # It takes several seconds for the tango database to be populated from
    # scratch, so pause until DB is created and the device we test against is
    # responsive. If the Tango DB volume already exists, there'll be no pause
    # delay at all and the test will run immediately.
	retry -- tango_admin --check-device sys/tg_test/1
	cd /app && ./test-harness/test_cli_profile.exp

.PHONY: all test
