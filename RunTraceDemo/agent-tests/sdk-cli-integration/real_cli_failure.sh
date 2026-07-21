#!/bin/sh
printf '%s\n' 'real-cli-child-before-failure' 'RUNTRACE_METRIC qa_score=8.0 step=1' 'RUNTRACE_EVENT level=error message="real CLI child failed"'
exit 23
