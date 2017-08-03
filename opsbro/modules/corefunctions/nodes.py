'''
classmatch
Table of Contents
Prototype: classmatch(regex, tag1, tag2, ...)
Return type: boolean
Description: Tests whether regex matches any currently set class.
Returns true if the anchored regular expression matches any currently defined class, otherwise returns false.
You can optionally restrict the search by tags, which you can list after the regular expression.
Example:
body common control
{
      bundlesequence  => { "example" };
}

bundle agent example
{
  classes:

      "do_it" and => { classmatch("cfengine_3.*"), "any" };
      "have_hardclass_nonesuch" expression => classmatch("nonesuchclass_sodonttryit", hardclass);
  reports:

    do_it::

      "Host matches pattern";

    have_hardclass_nonesuch::

      "Host has that really weird hardclass";
}
Output:
R: Host matches pattern
See also: canonify(), classify(), classesmatching()
'''


