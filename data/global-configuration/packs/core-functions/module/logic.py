'''
and
Table of Contents
Prototype: and(...)
Return type: string
Description: Returns any if all arguments evaluate to true and !any if any argument evaluates to false.
Arguments: A list of classes, class expressions, or functions that return classes.
Example:
    commands:
      "/usr/bin/generate_config $(config)"
        ifvarclass => and( "generating_configs",
                           not(fileexists("/etc/config/$(config)"))
                         );
Notes: Introduced primarily for use with ifvarclass, if, and unless promise attributes.
See Also: and, or, not
History: Was introduced in 3.2.0, Nova 2.1.0 (2011)
'''




'''
difference
Table of Contents
Prototype: difference(list1, list2)
Return type: slist
Description: Returns the unique elements in list1 that are not in list2.
This function can accept many types of data parameters.
Arguments:
list1: string, in the range: .*
list2: string, in the range: .*
Example:
body common control
{
      bundlesequence => { "test" };
}

bundle agent test
{
  vars:
      "a" slist => { 1,2,3,"x" };
      "b" slist => { "x" };

      # normal usage
      "diff_between_a_and_b" slist => difference(a, b);
      "diff_between_a_and_b_str" string => join(",", diff_between_a_and_b);

      # NOTE: advanced usage!
      "mylist1" slist => { "a", "b" };
      "mylist2" slist => { "a", "b" };
      "$(mylist1)_str" string => join(",", $(mylist1));

      # Here we're going to really call difference(a,a) then difference(a,b) then difference(b,a) then difference(b,b)
      # We create a new variable for each difference!!!
      "diff_$(mylist1)_$(mylist2)" slist => difference($(mylist1), $(mylist2));
      "diff_$(mylist1)_$(mylist2)_str" string => join(",", "diff_$(mylist1)_$(mylist2)");

  reports:
      # normal usage
      "The difference between lists a and b is '$(diff_between_a_and_b_str)'";

      # NOTE: advanced usage results!
      "The difference of list '$($(mylist1)_str)' with '$($(mylist2)_str)' is '$(diff_$(mylist1)_$(mylist2)_str)'";
}
Output:
R: The difference between lists a and b is '1,2,3'
R: The difference of list '1,2,3,x' with '1,2,3,x' is ''
R: The difference of list '1,2,3,x' with 'x' is '1,2,3'
R: The difference of list 'x' with '1,2,3,x' is ''
R: The difference of list 'x' with 'x' is ''
History: The collecting function behavior was added in 3.9.
See also: About collecting functions, intersection().

'''




'''
 every
Table of Contents
Prototype: every(regex, list)
Return type: boolean
Description: Returns whether every element in the variable list matches the unanchored regex.
This function can accept many types of data parameters.
Arguments:
regex : Regular expression to find, in the range .*
list : The name of the list variable to check, in the range [a-zA-Z0-9_$(){}\[\].:]+. It can be a data container or a regular list.
Example:
body common control
{
      bundlesequence => { "test" };
}

bundle agent test

{
  classes:
      "every_dot_star" expression => every(".*", test);
      "every_dot" expression => every(".", test);
      "every_number" expression => every("[0-9]", test);

      "every2_dot_star" expression => every(".*", test2);
      "every2_dot" expression => every(".", test2);
      "every2_number" expression => every("[0-9]", test2);

  vars:
      "test" slist => {
                        1,2,3,
                        "one", "two", "three",
                        "long string",
                        "four", "fix", "six",
                        "one", "two", "three",
      };

      "test2" data => parsejson('[1,2,3,
                        "one", "two", "three",
                        "long string",
                        "four", "fix", "six",
                        "one", "two", "three",]');

  reports:
      "The test list is $(test)";

    every_dot_star::
      "every() test passed: every element matches '.*'";
    !every_dot_star::
      "every() test failed: not every element matches '.*'";
    every_number::
      "every() test failed: every element matches '[0-9]'";
    !every_number::
      "every() test passed: not every element matches '[0-9]'";
    every_dot::
      "every() test failed: every element matches '.'";
    !every_dot::
      "every() test passed: not every element matches '.'";

      "The test2 list is $(test2)";
    every2_dot_star::
      "every() test2 passed: every element matches '.*'";
    !every2_dot_star::
      "every() test2 failed: not every element matches '.*'";
    every2_number::
      "every() test2 failed: every element matches '[0-9]'";
    !every2_number::
      "every() test2 passed: not every element matches '[0-9]'";
    every2_dot::
      "every() test2 failed: every element matches '.'";
    !every2_dot::
      "every() test2 passed: not every element matches '.'";
}
Output:
R: The test list is 1
R: The test list is 2
R: The test list is 3
R: The test list is one
R: The test list is two
R: The test list is three
R: The test list is long string
R: The test list is four
R: The test list is fix
R: The test list is six
R: every() test passed: every element matches '.*'
R: every() test passed: not every element matches '[0-9]'
R: every() test passed: not every element matches '.'
R: The test2 list is 1
R: The test2 list is 2
R: The test2 list is 3
R: The test2 list is one
R: The test2 list is two
R: The test2 list is three
R: The test2 list is long string
R: The test2 list is four
R: The test2 list is fix
R: The test2 list is six
R: every() test2 passed: every element matches '.*'
R: every() test2 passed: not every element matches '[0-9]'
R: every() test2 passed: not every element matches '.'
History: The collecting function behavior was added in 3.9.
See also: About collecting functions, filter(), some(), and none().
'''


'''
hash
Table of Contents
Prototype: hash(input, algorithm)
Return type: string
Description: Return the hash of input using the hash algorithm.
Hash functions are extremely sensitive to input. You should not expect to get the same answer from this function as you would from every other tool, since it depends on how whitespace and end of file characters are handled.
Arguments:
input: string, in the range: .*
algorithm: one of
md5
sha1
sha256
sha384
sha512
Example:
body common control
{
      bundlesequence => { "example" };
}

bundle agent example

{
  vars:

      "md5" string => hash("Cfengine is not cryptic","md5");
      "sha256" string => hash("Cfengine is not cryptic","sha256");
      "sha384" string => hash("Cfengine is not cryptic","sha384");
      "sha512" string => hash("Cfengine is not cryptic","sha512");

  reports:

      "Hashed to: md5 $(md5)";
      "Hashed to: sha256 $(sha256)";
      "Hashed to: sha384 $(sha384)";
      "Hashed to: sha512 $(sha512)";

}
Output:
R: Hashed to: md5 2036af0ee58d6d9dffcc6507af92664f
R: Hashed to: sha256 e2fb1927976bfe1ea3987c1a731c75e8ac1453d22a21811dc352db5e62d3f73c
R: Hashed to: sha384 b348c0b83ccd9ee12673f5daaba3ee5f49c42906540936bb16cf9d2001ed502b8c56f6e36b8389ab596febb529aab17f
R: Hashed to: sha512 29ce0883afbe7740bb2a016735499ae5a0a9b067539018ce6bb2c309a7e885c2d7da64744956e9f151bc72ec8dc19f85efd85eb0a73cbf1e829a15ac9ac35358
See also: file_hash()
'''


'''
hashmatch
Table of Contents
Prototype: hashmatch(filename, algorithm, hash)
Return type: boolean
Description: Compute the hash of file filename using the hash algorithm and test if it matches hash.
This function may be used to determine whether a system has a particular version of a binary file (e.g. software patch).
Arguments:
filename: string, in the range: "?(/.*)
algorithm: one of
md5
sha1
sha256
sha384
sha512
hash: string, in the range: [a-zA-Z0-9_$(){}\[\].:]+
hash is an ASCII representation of the hash for comparison.
Example:
bundle agent example
{
classes:

  "matches" expression => hashmatch("/etc/passwd","md5","c5068b7c2b1707f8939b283a2758a691");

reports:

  matches::

    "File has correct version";

}
'''



'''
intersection
Table of Contents
Prototype: intersection(list1, list2)
Return type: slist
Description: Returns the unique elements in list1 that are also in list2.
This function can accept many types of data parameters.
Arguments:
list1: string, in the range: .*
list2: string, in the range: .*
Example:
body common control
{
      bundlesequence => { "test" };
}

bundle agent test
{
  vars:
      "a" slist => { 1,2,3,"x" };
      "b" slist => { "x" };

      "mylist1" slist => { "a", "b" };
      "mylist2" slist => { "a", "b" };
      "$(mylist1)_str" string => join(",", $(mylist1));

      "int_$(mylist1)_$(mylist2)" slist => intersection($(mylist1), $(mylist2));
      "int_$(mylist1)_$(mylist2)_str" string => join(",", "int_$(mylist1)_$(mylist2)");

  reports:
      "The intersection of list '$($(mylist1)_str)' with '$($(mylist2)_str)' is '$(int_$(mylist1)_$(mylist2)_str)'";
}
Output:
R: The intersection of list '1,2,3,x' with '1,2,3,x' is '1,2,3,x'
R: The intersection of list '1,2,3,x' with 'x' is 'x'
R: The intersection of list 'x' with '1,2,3,x' is 'x'
R: The intersection of list 'x' with 'x' is 'x'
See also: About collecting functions, difference().
'''




'''
length
Table of Contents
Prototype: length(list)
Return type: int
Description: Returns the length of list.
This function can accept many types of data parameters.
Arguments:
list: string, in the range: .*
Example:
body common control
{
      bundlesequence => { "test" };
}

bundle agent test

{
  vars:
      "test" slist => {
                        1,2,3,
                        "one", "two", "three",
                        "long string",
                        "four", "fix", "six",
                        "one", "two", "three",
      };

      "length" int => length("test");
      "test_str" string => join(",", "test");

  reports:
      "The test list is $(test_str)";
      "The test list has $(length) elements";
}
Output:
R: The test list is 1,2,3,one,two,three,long string,four,fix,six,one,two,three
R: The test list has 13 elements
History: The collecting function behavior was added in 3.9.
See also: nth(), mergedata(), about collecting functions, and data documentation.
'''


'''
max
Table of Contents
Prototype: max(list, sortmode)
Return type: string
Description: Return the maximum of the items in list according to sortmode (same sort modes as in sort()).
This function can accept many types of data parameters.
Arguments:
list: string, in the range: .*
sortmode: one of
lex
int
real
IP
ip
MAC
mac
Example:
body common control
{
      bundlesequence => { "test" };
}

bundle agent test
{
  vars:
      # the behavior will be the same whether you use a data container or a list
      # "mylist" slist => { "foo", "1", "2", "3000", "bar", "10.20.30.40" };
      "mylist" data => parsejson('["foo", "1", "2", "3000", "bar", "10.20.30.40"]');
      "mylist_str" string => format("%S", mylist);

      "max_int" string => max(mylist, "int");
      "max_lex" string => max(mylist, "lex");
      "max_ip" string => max(mylist, "ip");

      "min_int" string => min(mylist, "int");
      "min_lex" string => min(mylist, "lex");
      "min_ip" string => min(mylist, "ip");

      "mean" real => mean(mylist);
      "variance" real => variance(mylist);

  reports:
      "my list is $(mylist_str)";

      "mean is $(mean)";
      "variance is $(variance) (use eval() to get the standard deviation)";

      "max int is $(max_int)";
      "max IP is $(max_ip)";
      "max lexicographically is $(max_lex)";

      "min int is $(min_int)";
      "min IP is $(min_ip)";
      "min lexicographically is $(min_lex)";
}
Output:
R: my list is ["foo","1","2","3000","bar","10.20.30.40"]
R: mean is 502.200000
R: variance is 1497376.000000 (use eval() to get the standard deviation)
R: max int is 3000
R: max IP is 10.20.30.40
R: max lexicographically is foo
R: min int is bar
R: min IP is 1
R: min lexicographically is 1
History: Was introduced in version 3.6.0 (2014). canonify mode was introduced in 3.9.0. The collecting function behavior was added in 3.9.
See also: sort(), variance(), sum(), mean(), min(), about collecting functions, and data documentation.

'''



'''
mean
Table of Contents
Prototype: mean(list)
Return type: real
Description: Return the mean of the numbers in list.
This function can accept many types of data parameters.
Arguments:
list: string, in the range: .*
Example:
body common control
{
      bundlesequence => { "test" };
}

bundle agent test
{
  vars:
      # the behavior will be the same whether you use a data container or a list
      # "mylist" slist => { "foo", "1", "2", "3000", "bar", "10.20.30.40" };
      "mylist" data => parsejson('["foo", "1", "2", "3000", "bar", "10.20.30.40"]');
      "mylist_str" string => format("%S", mylist);

      "max_int" string => max(mylist, "int");
      "max_lex" string => max(mylist, "lex");
      "max_ip" string => max(mylist, "ip");

      "min_int" string => min(mylist, "int");
      "min_lex" string => min(mylist, "lex");
      "min_ip" string => min(mylist, "ip");

      "mean" real => mean(mylist);
      "variance" real => variance(mylist);

  reports:
      "my list is $(mylist_str)";

      "mean is $(mean)";
      "variance is $(variance) (use eval() to get the standard deviation)";

      "max int is $(max_int)";
      "max IP is $(max_ip)";
      "max lexicographically is $(max_lex)";

      "min int is $(min_int)";
      "min IP is $(min_ip)";
      "min lexicographically is $(min_lex)";
}
Output:
R: my list is ["foo","1","2","3000","bar","10.20.30.40"]
R: mean is 502.200000
R: variance is 1497376.000000 (use eval() to get the standard deviation)
R: max int is 3000
R: max IP is 10.20.30.40
R: max lexicographically is foo
R: min int is bar
R: min IP is 1
R: min lexicographically is 1
History: Was introduced in version 3.6.0 (2014). The collecting function behavior was added in 3.9.
See also: sort(), variance(), sum(), max(), min(), about collecting functions, and data documentation.
'''



'''
min
Table of Contents
Prototype: min(list, sortmode)
Return type: string
Description: Return the minimum of the items in list according to sortmode (same sort modes as in sort()).
This function can accept many types of data parameters.
Arguments:
list: string, in the range: .*
sortmode: one of
lex
int
real
IP
ip
MAC
mac
Example:
body common control
{
      bundlesequence => { "test" };
}

bundle agent test
{
  vars:
      # the behavior will be the same whether you use a data container or a list
      # "mylist" slist => { "foo", "1", "2", "3000", "bar", "10.20.30.40" };
      "mylist" data => parsejson('["foo", "1", "2", "3000", "bar", "10.20.30.40"]');
      "mylist_str" string => format("%S", mylist);

      "max_int" string => max(mylist, "int");
      "max_lex" string => max(mylist, "lex");
      "max_ip" string => max(mylist, "ip");

      "min_int" string => min(mylist, "int");
      "min_lex" string => min(mylist, "lex");
      "min_ip" string => min(mylist, "ip");

      "mean" real => mean(mylist);
      "variance" real => variance(mylist);

  reports:
      "my list is $(mylist_str)";

      "mean is $(mean)";
      "variance is $(variance) (use eval() to get the standard deviation)";

      "max int is $(max_int)";
      "max IP is $(max_ip)";
      "max lexicographically is $(max_lex)";

      "min int is $(min_int)";
      "min IP is $(min_ip)";
      "min lexicographically is $(min_lex)";
}
Output:
R: my list is ["foo","1","2","3000","bar","10.20.30.40"]
R: mean is 502.200000
R: variance is 1497376.000000 (use eval() to get the standard deviation)
R: max int is 3000
R: max IP is 10.20.30.40
R: max lexicographically is foo
R: min int is bar
R: min IP is 1
R: min lexicographically is 1
History: Was introduced in version 3.6.0 (2014). The collecting function behavior was added in 3.9.
See also: sort(), variance(), sum(), max(), mean(), about collecting functions, and data documentation.
'''


'''
not
Table of Contents
Prototype: not(expression)
Return type: string
Description: Returns any if all arguments evaluate to false and !any if any argument evaluates to true.
Arguments:
expression: string, in the range: .*
Argument Descriptions:
expression - Class, class expression, or function that returns a class
Example:
commands:
  "/usr/bin/generate_config $(config)"
    ifvarclass => not( fileexists("/etc/config/$(config)") );
Notes: Introduced primarily for use with ifvarclass, if, and unless promise attributes.
See Also: and, or, not
History: Was introduced in 3.2.0, Nova 2.1.0 (2011)
'''


'''
nth
Table of Contents
Prototype: nth(list_or_container, position_or_key)
Return type: string
Description: Returns the element of list_or_container at zero-based position_or_key.
If an invalid position (below 0 or above the size of the list minus 1) or missing key is requested, this function does not return a valid value.
This function can accept many types of data parameters.
list_or_container can be an slist or a data container. If it's a slist, the offset is simply the position in the list. If it's a data container, the meaning of the position_or_key depends on its top-level contents: for a list like [1,2,3,4] you will get the list element at position_or_key. For a key-value map like { a: 100, b: 200 }, a position_or_key of a returns 100.
Arguments:
list_or_container: string, in the range: .*
position_or_key: string, in the range: .*
Example:
body common control
{
      bundlesequence => { "test" };
}

bundle agent test
{
  vars:
      "test" slist => {
                        1,2,3,
                        "one", "two", "three",
                        "long string",
                        "four", "fix", "six",
                        "one", "two", "three",
      };
      "test_str" string => format("%S", test);

      "test2" data => parsejson("[1, 2, 3, null]");
      "test2_str" string => format("%S", test2);

      "test3" data => parsejson('{ "x": true, "y": "z" }');
      "test3_str" string => format("%S", test3);

      "nth" slist => { 1, 2, 6, 10, 11, 1000 };
      "nth2" slist => getindices(test2);
      "nth3" slist => getindices(test3);

      "access[$(nth)]" string => nth(test, $(nth));
      "access[0]" string => nth(test, 0);

      "access2[$(nth2)]" string => nth(test2, $(nth2));
      "access3[$(nth3)]" string => nth(test3, $(nth3));

  reports:
      "The test list is $(test_str)";
      "element #$(nth) of the test list: $(access[$(nth)])";
      "element #0 of the test list: $(access[0])";

      "The test2 data container is $(test2_str)";
      "element #$(nth2) of the test2 data container: $(access2[$(nth2)])";

      "The test3 data container is $(test3_str)";
      "element #$(nth3) of the test3 data container: $(access3[$(nth3)])";
}
Output:
R: The test list is { "1", "2", "3", "one", "two", "three", "long string", "four", "fix", "six", "one", "two", "three" }
R: element #1 of the test list: 2
R: element #2 of the test list: 3
R: element #6 of the test list: long string
R: element #10 of the test list: one
R: element #11 of the test list: two
R: element #0 of the test list: 1
R: The test2 data container is [1,2,3,null]
R: element #0 of the test2 data container: 1
R: element #1 of the test2 data container: 2
R: element #2 of the test2 data container: 3
R: element #3 of the test2 data container: null
R: The test3 data container is {"x":true,"y":"z"}
R: element #x of the test3 data container: true
R: element #y of the test3 data container: z
History: The collecting function behavior was added in 3.9.
See also: length(), about collecting functions, and data documentation.
'''



'''
or
Table of Contents
Prototype: or(...)
Return type: string
Description: Returns any if any argument evaluates to true and !any if any argument evaluates to false.
Arguments: A list of classes, class expressions, or functions that return classes.
Example:
    commands:
      "/usr/bin/generate_config $(config)"
        ifvarclass => or( "force_configs",
                          not(fileexists("/etc/config/$(config)"))
                        );
Notes: Introduced primarily for use with ifvarclass, if, and unless promise attributes.
See Also: and, or, not
History: Was introduced in 3.2.0, Nova 2.1.0 (2011)
'''



'''
parsejson
Table of Contents
Prototype: parsejson(json_data)
Return type: data
Description: Parses JSON data directly from an inlined string and returns the result as a data variable
Arguments:
json_data: string, in the range: .*
Please note that because JSON uses double quotes, it's usually most convenient to use single quotes for the string (CFEngine allows both types of quotes around a string).
This function can accept many types of data parameters.
Example:
    vars:

      "loadthis"

         data =>  parsejson('{ "key": "value" }');

      # inline syntax since 3.7
      "loadthis_inline"

         data =>  '{ "key": "value" }';
History: The collecting function behavior was added in 3.9.
See also: readjson(), parseyaml(), readyaml(), mergedata(), Inline YAML and JSON data, about collecting functions, and data documentation.
'''



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


'''
randomint
Table of Contents
Prototype: randomint(lower, upper)
Return type: int
Description: Returns a random integer between lower and up to but not including upper.
The limits must be integer values and the resulting numbers are based on the entropy of the md5 algorithm.
The upper limit is excluded from the range. Thus randomint(0, 100) will return 100 possible values, not 101.
The function will be re-evaluated on each pass if it is not restricted with a context class expression as shown in the example.
NOTE: The randomness produced by randomint is not safe for cryptographic usage.
Arguments:
lower: int, in the range: -99999999999,99999999999
upper: int, in the range: -99999999999,99999999999
Example:
bundle agent main
{
  vars:
      "low"    string => "4";
      "high"   string => "60";

      "random"    int => randomint($(low), $(high));
  classes:
      "isabove" expression => isgreaterthan($(random), 3);

  reports:
    isabove::
      "The generated random number was above 3";

    show_random::
      "Randomly generated '$(random)'";
}
Output: (when show_random is defined)
R: The generated random number was above 3
R: Randomly generated '9'
R: Randomly generated '52'
R: Randomly generated '26'

'''



'''
regextract
Table of Contents
Prototype: regextract(regex, string, backref)
Return type: boolean
Description: Returns whether the anchored regex matches the string, and fills the array backref with back-references.
This function should be avoided in favor of data_regextract() because it creates classic CFEngine array variables and does not support named captures.
If there are any back reference matches from the regular expression, then the array will be populated with the values, in the manner:
    $(backref[0]) = entire string
    $(backref[1]) = back reference 1, etc
Arguments:
regex: regular expression, in the range: .*
string: string, in the range: .*
backref: string, in the range: [a-zA-Z0-9_$(){}\[\].:]+
Example:
body common control
{
      bundlesequence => { "example" };
}

bundle agent example
{
  classes:

      # Extract regex backreferences and put them in an array

      "ok" expression => regextract(
                                     "xx ([^\s]+) ([^\s]+).* xx",
                                     "xx one two three four xx",
                                     "myarray"
      );
  reports:

    ok::

      "ok - \"$(myarray[0])\" = xx + \"$(myarray[1])\" + \"$(myarray[2])\" + .. + xx";
}
Output:
R: ok - "xx one two three four xx" = xx + "one" + "two" + .. + xx
See also: data_regextract() regex_replace()
'''



'''
reverse
Table of Contents
Prototype: reverse(list)
Return type: slist
Description: Reverses a list.
This is a simple function to reverse a list.
This function can accept many types of data parameters.
Arguments:
list : The name of the list variable to check, in the range [a-zA-Z0-9_$(){}\[\].:]+
Example:
body common control
{
      bundlesequence => { "test" };
}

bundle agent test
{
  vars:
      "test" slist => {
                        1,2,3,
                        "one", "two", "three",
                        "long string",
                        "one", "two", "three",
      };

      "reversed" slist => reverse("test");

  reports:
      "Original list is $(test)";
      "The reversed list is $(reversed)";
}
Output:
R: Original list is 1
R: Original list is 2
R: Original list is 3
R: Original list is one
R: Original list is two
R: Original list is three
R: Original list is long string
R: The reversed list is three
R: The reversed list is two
R: The reversed list is one
R: The reversed list is long string
R: The reversed list is 3
R: The reversed list is 2
R: The reversed list is 1
History: The collecting function behavior was added in 3.9.
See also: filter(), grep(), every(), some(), none(), about collecting functions, and data documentation.
'''


'''
reglist
Table of Contents
Prototype: reglist(list, regex)
Return type: boolean
Description: Returns whether the anchored regular expression regex matches any item in list.
This function can accept many types of data parameters.
Arguments:
list: string, in the range: .*
regex: regular expression, in the range: .*
Example:
body common control
{
      bundlesequence => { "example" };
}

bundle agent example
{
  vars:

      "nameservers" slist => {
                               "128.39.89.10",
                               "128.39.74.16",
                               "192.168.1.103",
                               "10.132.51.66"
      };
  classes:

      "am_name_server" expression => reglist(@(nameservers), "127\.0\.0\.1");
  reports:
    am_name_server::
      "127.0.0.1 is currently set as a nameserver";
    !am_name_server::
      "127.0.0.1 is NOT currently set as a nameserver";
}
Output:
R: 127.0.0.1 is NOT currently set as a nameserver
In the example above, the IP address in $(sys.ipv4[eth0]) must be escaped, so that the (.) characters in the IP address are not interpreted as the regular expression "match any" characters.
History: The collecting function behavior was added in 3.9.
See also: getindices(), getvalues(), about collecting functions, and data documentation.
'''



'''
shuffle
Table of Contents
Prototype: shuffle(list, seed)
Return type: slist
Description: Return list shuffled with seed.
This function can accept many types of data parameters.
The same seed will produce the same shuffle every time. For a random shuffle, provide a random seed with the randomint function.
Arguments:
list: string, in the range: .*
seed: string, in the range: .*
Example:
body common control
{
      bundlesequence => { "test" };
}

bundle agent test
{
  vars:
      "mylist" slist => { "b", "c", "a" };
      "seeds" slist => { "xx", "yy", "zz" };

      "shuffled_$(seeds)" slist => shuffle(mylist, $(seeds));

      "joined_$(seeds)" string => join(",", "shuffled_$(seeds)");

  reports:
      "shuffled RANDOMLY by $(seeds) = '$(joined_$(seeds))'";
}
Output:
R: shuffled RANDOMLY by xx = 'b,a,c'
R: shuffled RANDOMLY by yy = 'a,c,b'
R: shuffled RANDOMLY by zz = 'c,b,a'
History: The collecting function behavior was added in 3.9.
See also: sort(), about collecting functions, and data documentation.
'''



'''
sort
Table of Contents
Prototype: sort(list, mode)
Return type: slist
Description: Returns list sorted according to mode.
This function can accept many types of data parameters.
Lexicographical, integer, real, IP, and MAC address sorting is supported currently. The example below will show each sorting mode in action. mode is optional, and defaults to lex.
Note IPv6 addresses can not use uppercase hexadecimal characters (A-Z) but must use lowercase (a-z) instead.
Arguments:
list: string, in the range: .*
mode: one of
lex
int
real
IP
ip
MAC
mac
Example:
body common control
{
      bundlesequence => { test };
}

bundle agent test
{
  vars:
      "a" slist => { "b", "c", "a" };
      "b" slist => { "100", "9", "10", "8.23" };
      "c" slist => { };
      "d" slist => { "", "a", "", "b" };
      "e" slist => { "a", "1", "b" };

      "ips" slist => { "100.200.100.0", "1.2.3.4", "9.7.5.1", "9", "9.7", "9.7.5", "", "-1", "where are the IP addresses?" };
      "ipv6" slist => { "FE80:0000:0000:0000:0202:B3FF:FE1E:8329",
                        "FE80::0202:B3FF:FE1E:8329",
                        "::1",
                        # the following should all be parsed as the same address and sorted together
                        "2001:db8:0:0:1:0:0:1",
                        "2001:0db8:0:0:1:0:0:1",
                        "2001:db8::1:0:0:1",
                        "2001:db8::0:1:0:0:1",
                        "2001:0db8::1:0:0:1",
                        "2001:db8:0:0:1::1",
                        "2001:db8:0000:0:1::1",
                        "2001:DB8:0:0:1::1", # note uppercase IPv6 addresses are invalid
                        # examples from https://www.ripe.net/lir-services/new-lir/ipv6_reference_card.pdf
                        "8000:63bf:3fff:fdd2",
                        "::ffff:192.0.2.47",
                        "fdf8:f53b:82e4::53",
                        "fe80::200:5aee:feaa:20a2",
                        "2001:0000:4136:e378:",
                        "8000:63bf:3fff:fdd2",
                        "2001:0002:6c::430",
                        "2001:10:240:ab::a",
                        "2002:cb0a:3cdd:1::1",
                        "2001:db8:8:4::2",
                        "ff01:0:0:0:0:0:0:2",
                        "-1", "where are the IP addresses?" };

      "macs" slist => { "00:14:BF:F7:23:1D", "0:14:BF:F7:23:1D", ":14:BF:F7:23:1D", "00:014:BF:0F7:23:01D",
                        "00:14:BF:F7:23:1D", "0:14:BF:F7:23:1D", ":14:BF:F7:23:1D", "00:014:BF:0F7:23:01D",
                        "01:14:BF:F7:23:1D", "1:14:BF:F7:23:1D",
                        "01:14:BF:F7:23:2D", "1:14:BF:F7:23:2D",
                        "-1", "where are the MAC addresses?" };

      "ja" string => join(",", "a");
      "jb" string => join(",", "b");
      "jc" string => join(",", "c");
      "jd" string => join(",", "d");
      "je" string => join(",", "e");

      "jips" string => join(",", "ips");
      "jipv6" string => join(",", "ipv6");
      "jmacs" string => join(",", "macs");

      "sa" slist => sort("a", "lex");
      "sb" slist => sort("b", "lex");
      "sc" slist => sort("c", "lex");
      "sd" slist => sort("d", "lex");
      "se" slist => sort("e", "lex");

      "sb_int" slist => sort("b", "int");
      "sb_real" slist => sort("b", "real");

      "sips" slist => sort("ips", "ip");
      "sipv6" slist => sort("ipv6", "ip");
      "smacs" slist => sort("macs", "mac");


      "jsa" string => join(",", "sa");
      "jsb" string => join(",", "sb");
      "jsc" string => join(",", "sc");
      "jsd" string => join(",", "sd");
      "jse" string => join(",", "se");

      "jsb_int" string => join(",", "sb_int");
      "jsb_real" string => join(",", "sb_real");

      "jsips" string => join(",", "sips");
      "jsipv6" string => join(",", "sipv6");
      "jsmacs" string => join(",", "smacs");

  reports:
      "sorted lexicographically '$(ja)' => '$(jsa)'";
      "sorted lexicographically '$(jb)' => '$(jsb)'";
      "sorted lexicographically '$(jc)' => '$(jsc)'";
      "sorted lexicographically '$(jd)' => '$(jsd)'";
      "sorted lexicographically '$(je)' => '$(jse)'";

      "sorted integers '$(jb)' => '$(jsb_int)'";
      "sorted reals '$(jb)' => '$(jsb_real)'";

      "sorted IPs '$(jips)' => '$(jsips)'";
      "sorted IPv6s '$(jipv6)' => '$(jsipv6)'";
      "sorted MACs '$(jmacs)' => '$(jsmacs)'";
}
Output:
2013-09-05T14:05:04-0400   notice: R: sorted lexicographically 'b,c,a' => 'a,b,c'
2013-09-05T14:05:04-0400   notice: R: sorted lexicographically '100,9,10,8.23' => '10,100,8.23,9'
2013-09-05T14:05:04-0400   notice: R: sorted lexicographically '' => ''
2013-09-05T14:05:04-0400   notice: R: sorted lexicographically ',a,,b' => ',,a,b'
2013-09-05T14:05:04-0400   notice: R: sorted lexicographically 'a,1,b' => '1,a,b'
2013-09-05T14:05:04-0400   notice: R: sorted integers '100,9,10,8.23' => '8.23,9,10,100'
2013-09-05T14:05:04-0400   notice: R: sorted reals '100,9,10,8.23' => '8.23,9,10,100'
2013-09-05T14:05:04-0400   notice: R: sorted IPs '100.200.100.0,1.2.3.4,9.7.5.1,9,9.7,9.7.5,,-1,where are the IP addresses?' => ',-1,9,9.7,9.7.5,where are the IP addresses?,1.2.3.4,9.7.5.1,100.200.100.0'
2013-09-05T14:05:04-0400   notice: R: sorted IPv6s 'FE80:0000:0000:0000:0202:B3FF:FE1E:8329,FE80::0202:B3FF:FE1E:8329,::1,2001:db8:0:0:1:0:0:1,2001:0db8:0:0:1:0:0:1,2001:db8::1:0:0:1,2001:db8::0:1:0:0:1,2001:0db8::1:0:0:1,2001:db8:0:0:1::1,2001:db8:0000:0:1::1,2001:DB8:0:0:1::1,8000:63bf:3fff:fdd2,::ffff:192.0.2.47,fdf8:f53b:82e4::53,fe80::200:5aee:feaa:20a2,2001:0000:4136:e378:,8000:63bf:3fff:fdd2,2001:0002:6c::430,2001:10:240:ab::a,2002:cb0a:3cdd:1::1,2001:db8:8:4::2,ff01:0:0:0:0:0:0:2,-1,where are the IP addresses?' => '-1,2001:0000:4136:e378:,2001:DB8:0:0:1::1,8000:63bf:3fff:fdd2,8000:63bf:3fff:fdd2,::ffff:192.0.2.47,FE80:0000:0000:0000:0202:B3FF:FE1E:8329,FE80::0202:B3FF:FE1E:8329,where are the IP addresses?,::1,2001:0002:6c::430,2001:10:240:ab::a,2001:db8:0000:0:1::1,2001:db8:0:0:1::1,2001:0db8::1:0:0:1,2001:db8::0:1:0:0:1,2001:db8::1:0:0:1,2001:0db8:0:0:1:0:0:1,2001:db8:0:0:1:0:0:1,2001:db8:8:4::2,2002:cb0a:3cdd:1::1,fdf8:f53b:82e4::53,fe80::200:5aee:feaa:20a2,ff01:0:0:0:0:0:0:2'
2013-09-05T14:05:04-0400   notice: R: sorted MACs '00:14:BF:F7:23:1D,0:14:BF:F7:23:1D,:14:BF:F7:23:1D,00:014:BF:0F7:23:01D,00:14:BF:F7:23:1D,0:14:BF:F7:23:1D,:14:BF:F7:23:1D,00:014:BF:0F7:23:01D,01:14:BF:F7:23:1D,1:14:BF:F7:23:1D,01:14:BF:F7:23:2D,1:14:BF:F7:23:2D,-1,where are the MAC addresses?' => '-1,:14:BF:F7:23:1D,:14:BF:F7:23:1D,where are the MAC addresses?,00:014:BF:0F7:23:01D,0:14:BF:F7:23:1D,00:14:BF:F7:23:1D,00:014:BF:0F7:23:01D,0:14:BF:F7:23:1D,00:14:BF:F7:23:1D,1:14:BF:F7:23:1D,01:14:BF:F7:23:1D,1:14:BF:F7:23:2D,01:14:BF:F7:23:2D'
History: - Function added in 3.6.0. - Collecting function behavior added in 3.9.0. - Optional mode defaulting to lex behavior added in 3.9.0.
See also: shuffle(), about collecting functions, and data documentation.
'''


'''
storejson
Table of Contents
Prototype: storejson(data_container)
Return type: string
Description: Converts a data container to a JSON string.
This function can accept many types of data parameters.
Arguments:
data_container: string, in the range: .*
Example:
   vars:

      "loadthis"
         data =>  readjson("/tmp/data.json", 4000);
      "andback"
         string =>  storejson(loadthis);
   reports:
      "Converted /tmp/data.json to '$(andback)'";
History: The collecting function behavior was added in 3.9.
See also: readjson(), readyaml(), parsejson(), parseyaml(), about collecting functions, and data documentation.
'''

'''
sum
Table of Contents
Prototype: sum(list)
Return type: real
Description: Return the sum of the reals in list.
This function can accept many types of data parameters.
This function might be used for simple ring computation. Of course, you could easily combine sum with readstringarray or readreallist etc., to collect summary information from a source external to CFEngine.
Arguments:
list: string, in the range: .*
Example:
body common control
{
      bundlesequence => { "test" };
}

bundle agent test
{
  vars:
      "adds_to_six" ilist => { "1", "2", "3" };
      "six" real => sum("adds_to_six");
      "adds_to_zero" rlist => { "1.0", "2", "-3e0" };
      "zero" real => sum("adds_to_zero");

  reports:
      "six is $(six), zero is $(zero)";
}
Output:
R: six is 6.000000, zero is 0.000000
Because $(six) and $(zero) are both real numbers, the report that is generated will be:
six is 6.000000, zero is 0.000000
Notes:
History: Was introduced in version 3.1.0b1,Nova 2.0.0b1 (2010). The collecting function behavior was added in 3.9.
See also: product(), about collecting functions, and data documentation.
'''



'''
unique
Table of Contents
Prototype: unique(list)
Return type: slist
Description: Returns list of unique elements from list.
This function can accept many types of data parameters.
Arguments:
list: string, in the range: .*
Example:
body common control
{
      bundlesequence => { "test" };
}

bundle agent test
{
  vars:
      "test" slist => {
                        1,2,3,
                        "one", "two", "three",
                        "long string",
                        "four", "fix", "six",
                        "one", "two", "three",
      };

      "test_str" string => join(",", "test");
      "test_unique" slist => unique("test");
      "unique_str" string => join(",", "test_unique");

  reports:
      "The test list is $(test_str)";
      "The unique elements of the test list: $(unique_str)";
}
Output:
R: The test list is 1,2,3,one,two,three,long string,four,fix,six,one,two,three
R: The unique elements of the test list: 1,2,3,one,two,three,long string,four,fix,six
History: The collecting function behavior was added in 3.9.
See also: filter(), about collecting functions, and data documentation.
'''