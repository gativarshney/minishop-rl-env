#!/bin/bash
# Runs a command; if it fails, copies the end of its output into a CI annotation
# so the reason can be read without opening the full log.
"$@" > step.log 2>&1
code=$?
cat step.log
if [ $code -ne 0 ]; then
  echo "::error::[page mode ${MINISHOP_PAGE_MODE:-default}] $(tail -c 900 step.log | tr '\n' ' ')"
fi
exit $code
