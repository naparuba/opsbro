#!/usr/bin/env bash

# Load common shell functions
MYDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. $MYDIR/common_shell_functions.sh

#
# Author: Brian Beffa <brbsix@gmail.com>
# Original source: https://brbsix.github.io/2015/11/29/accessing-tab-completion-programmatically-in-bash/
# License: LGPLv3 (http://www.gnu.org/licenses/lgpl-3.0.txt)
#
get_completions() {
   local completion COMP_CWORD COMP_LINE COMP_POINT COMP_WORDS COMPREPLY=()

   # load bash-completion if necessary
   declare -F _completion_loader &>/dev/null || {
      source /usr/share/bash-completion/bash_completion
   }

   COMP_LINE=$*
   COMP_POINT=${#COMP_LINE}

   eval set -- "$@"

   COMP_WORDS=("$@")

    # add '' to COMP_WORDS if the last character of the command line is a space
    [[ ${COMP_LINE[@]: -1} = ' ' ]] && COMP_WORDS+=('')

   # index of the last word
   COMP_CWORD=$((${#COMP_WORDS[@]} - 1))

   # determine completion function
   completion=$(complete -p "$1" 2>/dev/null | awk '{print $(NF-1)}')

   # run _completion_loader only if necessary
   [[ -n $completion ]] || {

      # load completion
      _completion_loader "$1"

      # detect completion
      completion=$(complete -p "$1" 2>/dev/null | awk '{print $(NF-1)}')

   }

   # ensure completion was detected
   [[ -n $completion ]] || return 1

   # execute completion function
   "$completion"

   # print completions to stdout
   printf '%s\n' "${COMPREPLY[@]}" | LC_ALL=C sort
}

get_completions 'opsbro agent inf ' | grep 'info'
if [ $? != 0 ]; then
   echo "ERROR: should be completion available"
   get_completions 'opsbro agent inf '
   exit 2
fi

print_header "OK completion seems to be working"
get_completions 'opsbro agent inf '

exit_if_no_crash "Ok completion"
