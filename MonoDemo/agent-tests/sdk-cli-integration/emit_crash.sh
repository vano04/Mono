#!/bin/sh
printf '%s\n' 'child-before-crash' 'MONO_METRIC loss=9.5 step=1' 'MONO_EVENT level=error message="child will fail"'
exit 17
