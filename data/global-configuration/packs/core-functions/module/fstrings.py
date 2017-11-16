from opsbro.evaluater import export_evaluater_function

FUNCTION_GROUP = 'string'


@export_evaluater_function(function_group=FUNCTION_GROUP)
def string_upper(string):
    """**string_upper(string)** -> return the upercase value of the string

 * string: (string) string to upper case.


<code>
    Example:
        string_upper('linux')
    Returns:
        'LINUX'
</code>
    """
    return string.upper()


@export_evaluater_function(function_group=FUNCTION_GROUP)
def string_lower(string):
    """**string_lower(string)** -> return the lowercase value of the string

 * string: (string) string to lower case.


<code>
    Example:
        string_lower('Linux')
    Returns:
        'linux'
</code>
    """
    return string.lower()


@export_evaluater_function(function_group=FUNCTION_GROUP)
def string_split(string, split_character):
    """**string_split(string, split_character)** -> return a list with the string splitted by the split_caracter

 * string: (string) string to split case.
 * split_character: (string) string to use to split


<code>
    Example:
        string_split('linux,windows', ',')
    Returns:
        ['linux', 'windows']
</code>
    """
    return string.split(split_character)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def string_join(list, join_character):
    """**string_join(string, join_character)** -> return a string with elements for the lsit joined by the join_character

 * list: (list of strings) list of string to joins
 * join_character: (string) character to user between strings


<code>
    Example:
        string_join(['linux', 'windows'], ',')
    Returns:
        'linux,windows'
</code>
    """
    return join_character.join(list)


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
