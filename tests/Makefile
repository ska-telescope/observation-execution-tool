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
	mkdir -p build && \
	tox -e py37 | tee build/pytest.stdout && \
	status=$$?; \
	exit $$status

lint:
	mkdir -p build/reports && \
	tox -e lint | tee build/lint.stdout

.PHONY: all test install lint
