#!/usr/bin/env bash
echo "STATIC CODE ANALYSIS"
echo "===================="
echo

echo "MODULE ANALYSIS"
echo "---------------"
pylint oet

echo "TESTS ANALYSIS"
echo "--------------"
pylint tests
