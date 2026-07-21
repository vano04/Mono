#!/bin/sh
printf '%s\n' 'child-before-crash' 'RUNTRACE_METRIC loss=9.5 step=1' 'RUNTRACE_EVENT level=error message="child will fail"'
exit 17
