import copy

from opsbro.evaluater import export_evaluater_function

FUNCTION_GROUP = 'set'


@export_evaluater_function(function_group=FUNCTION_GROUP)
def set_difference(in_this_set1, but_not_in_this_set2):
    """**set_difference(in_this_set, but_not_in_this_set)** -> Returns the elements that are in the set1 but not on the set2

<code>
    Example:

        set_difference(set([1, 2, 3, 4]), set([2, 3]))

    Returns:

        set([1, 4])

</code>

    """
    s1 = set(in_this_set1)
    s2 = set(but_not_in_this_set2)
    return s1.difference(s2)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def set_intersection(in_this_set1, and_in_this_set2):
    """**set_intersection(in_this_set1, and_in_this_set2)** -> Returns the elements that are in the set1 and on the set2

<code>
    Example:

        set_intersection(set([1, 2, 3, 4]), set([3, 4, 5, 6]))

    Returns:

        set([3, 4])

</code>

    """
    s1 = set(in_this_set1)
    s2 = set(and_in_this_set2)
    return s1.intersection(s2)


@export_evaluater_function(function_group='basic')
def reverse(list):
    """**reverse(list)** -> Returns a list tha is the reverse order of the input

<code>
    Example:

        reverse( [ 1, 2, 3 ] )

    Returns:

        [3, 2, 1]

</code>

    """
    n_list = copy.copy(list)
    n_list.reverse()
    return n_list


'''
parseyaml
Table of Contents
Prototype: parseyaml(yaml_data)
Return type: data
Description: Parses YAML data directly from an inlined string and returns the result as a data variable
Arguments:
yaml_data: string, in the range: .*
Please note that it's usually most convenient to use single quotes for the string (CFEngine allows both types of quotes around a string).
Example:
    vars:

      "loadthis"

      data =>  parseyaml('
    - arrayentry1
    - arrayentry2
    - key1: 1
      key2: 2
    ');

      # inline syntax since 3.7
      # note the --- preamble is required with inline data
      "loadthis_inline"

      data =>  '---
    - arrayentry1
    - arrayentry2
    - key1: 1
      key2: 2
    ';
See also: readjson(), readyaml(), mergedata(), Inline YAML and JSON data, and data documentation.
'''
