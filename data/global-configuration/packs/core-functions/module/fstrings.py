'''
concat
Table of Contents
Prototype: concat(...)
Return type: string
Description: Concatenates all arguments into a string.
Example:
    commands:
      "/usr/bin/generate_config $(config)"
        ifvarclass => concat("have_config_", canonify("$(config)"));
History: Was introduced in 3.2.0, Nova 2.1.0 (2011)
'''





'''
escape
Table of Contents
Prototype: escape(text)
Return type: string
Description: Escape regular expression characters in text.
This function is useful for making inputs readable when a regular expression is required, but the literal string contains special characters. The function simply 'escapes' all the regular expression characters, so that you do not have to.
Arguments:
path: string, in the range: .*
Example:
body common control
{
      bundlesequence => { "example" };
}

bundle agent example
{
  vars:
      "ip" string => "10.123.321.250";
      "escaped" string => escape($(ip));

  reports:
      "escaped $(ip) = $(escaped)";
}
Output:
R: escaped 10.123.321.250 = 10\.123\.321\.250
In this example, the string "192.168.2.1" is "escaped" to be equivalent to "192\.168\.2\.1", because without the backslashes, the regular expression "192.168.2.1" will also match the IP ranges "192.168.201", "192.168.231", etc (since the dot character means "match any character" when used in a regular expression).
Notes:
History: This function was introduced in CFEngine version 3.0.4 (2010)
'''


'''
format
Table of Contents
Prototype: format(string, ...)
Return type: string
Description: Applies sprintf-style formatting to a given string.
This function will format numbers (o, x, d and f) or strings (s) but not potentially dangerous things like individual characters or pointer offsets.
The %S specifier is special and non-standard. When you use it on a slist or a data container, the data will be packed into a one-line string you can put in a log message, for instance.
This function will fail if it doesn't have enough arguments; if any format specifier contains the modifiers hLqjzt; or if any format specifier is not one of doxfsS.
Example:
body common control
{
      bundlesequence => { "run" };
}

bundle agent run
{
  vars:
      "v" string => "2.5.6";
      "vlist" slist => splitstring($(v), "\.", 3);
      "padded" string => format("%04d%04d%04d", nth("vlist", 0), nth("vlist", 1), nth("vlist", 2));
      "a" string => format("%10.10s", "x");
      "b" string => format("%-10.10s", "x");
      "c" string => format("%04d", 1);
      "d" string => format("%07.2f", 1);
      "e" string => format("hello my name is %s %s", "Inigo", "Montoya");

      "container" data => parsejson('{ "x": "y", "z": true }');

      "packed" string => format("slist = %S, container = %S", vlist, container);

  reports:
      "version $(v) => padded $(padded)";
      "%10.10s on 'x' => '$(a)'";
      "%-10.10s on 'x' => '$(b)'";
      "%04d on '1' => '$(c)'";
      "%07.2f on '1' => '$(d)'";
      "you killed my father... => '$(e)'";
      "$(packed)";
}
Output:
R: version 2.5.6 => padded 000200050006
R: %10.10s on 'x' => '         x'
R: %-10.10s on 'x' => 'x         '
R: %04d on '1' => '0001'
R: %07.2f on '1' => '0001.00'
R: you killed my father... => 'hello my name is Inigo Montoya'
R: slist = { "2", "5", "6" }, container = {"x":"y","z":true}
Note: the underlying sprintf system call may behave differently on some platforms for some formats. Test carefully. For example, the format %08s will use spaces to fill the string up to 8 characters on libc platforms, but on Darwin (Mac OS X) it will use zeroes. According to SUSv4 the behavior is undefined for this specific case.
'''

'''
join
Table of Contents
Prototype: join(glue, list)
Return type: string
Description: Join the items of list into a string, using the conjunction in glue.
Converts a list or data container into a scalar variable using the join string in first argument.
This function can accept many types of data parameters.
Arguments:
glue: string, in the range: .*
list: string, in the range: .*
Example:
body common control
{
      bundlesequence => { "test" };
}

bundle agent test
{
  vars:

      "mylist" slist => { "one", "two", "three", "four", "five" };
      "datalist" data => parsejson('[1,2,3,
                        "one", "two", "three",
                        "long string",
                        "four", "fix", "six",
                        "one", "two", "three",]');

      "mylist_str" string => format("%S", mylist);
      "datalist_str" string => format("%S", datalist);
      "myscalar" string => join("->", mylist);
      "datascalar" string => join("->", datalist);

  reports:
      "Concatenated $(mylist_str): $(myscalar)";
      "Concatenated $(datalist_str): $(datascalar)";
}
Output:
R: Concatenated { "one", "two", "three", "four", "five" }: one->two->three->four->five
R: Concatenated [1,2,3,"one","two","three","long string","four","fix","six","one","two","three"]: 1->2->3->one->two->three->long string->four->fix->six->one->two->three
History: The collecting function behavior was added in 3.9.
See also: string_split(), about collecting functions.
'''


'''
splitstring
Table of Contents
Prototype: splitstring(string, regex, maxent)
Return type: slist
Description: Splits string into at most maxent substrings wherever regex occurs, and returns the list with those strings.
The regular expression is unanchored.
If the maximum number of substrings is insufficient to accommodate all the entries, the rest of the un-split string is thrown away.
Arguments:
string: string, in the range: .*
regex: regular expression, in the range: .*
maxent: int, in the range: 0,99999999999
Example:
body common control
{
      bundlesequence => { "test" };
}

bundle agent test
{
  vars:

      "split1" slist => splitstring("one:two:three",":","10");
      "split2" slist => splitstring("one:two:three",":","1");
      "split3" slist => splitstring("alpha:xyz:beta","xyz","10");

  reports:

      "split1: $(split1)";  # will list "one", "two", and "three"
      "split2: $(split2)";  # will list "one", "two:three" will be thrown away.
      "split3: $(split3)";  # will list "alpha:" and ":beta"

}
Output:
R: split1: one
R: split1: two
R: split1: three
R: split2: one
R: split3: alpha:
R: split3: :beta
History: Deprecated in CFEngine 3.6 in favor of string_split
See also: string_split()
'''


'''
string_downcase
Table of Contents
Prototype: string_downcase(data)
Return type: string
Description: Returns data in lower case.
Arguments:
data: string, in the range: .*
Example:
body common control
{
      bundlesequence => { "example" };
}

bundle agent example
{
  vars:
      "downcase" string => string_downcase("ABC"); # will contain "abc"
  reports:
      "downcased ABC = $(downcase)";
}
Output:
R: downcased ABC = abc
History: Introduced in CFEngine 3.6
See also: string_upcase().
'''


'''
string_length
Table of Contents
Prototype: string_length(data)
Return type: int
Description: Returns the byte length of data.
Arguments:
data: string, in the range: .*
Example:
body common control
{
      bundlesequence => { "example" };
}

bundle agent example
{
  vars:
      "length" int =>  string_length("abc"); # will contain "3"
  reports:
      "length of string abc = $(length)";
}
Output:
R: length of string abc = 3
History: Introduced in CFEngine 3.6
See also: string_head(), string_tail(), string_reverse().
'''



'''
string_upcase
Table of Contents
Prototype: string_upcase(data)
Return type: string
Description: Returns data in uppercase.
Arguments:
data: string, in the range: .*
Example:
body common control
{
      bundlesequence => { "example" };
}

bundle agent example
{
  vars:
      "upcase" string => string_upcase("abc"); # will contain "ABC"
  reports:
      "upcased abc: $(upcase)";
}
Output:
R: upcased abc: ABC
History: Introduced in CFEngine 3.6
See also: string_downcase().
'''


'''
string_split
Table of Contents
Prototype: string_split(string, regex, maxent)
Return type: slist
Description: Splits string into at most maxent substrings wherever regex occurs, and returns the list with those strings.
The regular expression is unanchored.
If the maximum number of substrings is insufficient to accommodate all the entries, the generated slist will have maxent items and the last one will contain the rest of the string starting with the maxent-1-th delimiter. This is standard behavior in many languages like Perl or Ruby, and different from the splitstring() behavior.
Arguments:
string: string, in the range: .*
regex: regular expression, in the range: .*
maxent: int, in the range: 0,99999999999
Example:
body common control
{
      bundlesequence => { "test" };
}

bundle agent test
{
  vars:

      "split1" slist => string_split("one:two:three", ":", "10");
      "split2" slist => string_split("one:two:three", ":", "1");
      "split3" slist => string_split("alpha:xyz:beta", "xyz", "10");

  reports:

      "split1: $(split1)";  # will list "one", "two", and "three"
      "split2: $(split2)";  # will list "one:two:three"
      "split3: $(split3)";  # will list "alpha:" and ":beta"

}
Output:
R: split1: one
R: split1: two
R: split1: three
R: split2: one:two:three
R: split3: alpha:
R: split3: :beta
History: Introduced in CFEngine 3.6; deprecates splitstring().
See also: splitstring()
'''