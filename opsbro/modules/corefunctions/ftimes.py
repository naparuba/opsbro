'''
ago
Table of Contents
Prototype: ago(years, months, days, hours, minutes, seconds)
Return type: int
Description: Convert a time relative to now to an integer system representation.
The ago function measures time relative to now. Arguments are applied in order, so that ago(0,18,55,27,0,0) means "18 months, 55 days, and 27 hours ago". However, you are strongly encouraged to keep your usage of ago sensible and readable, e.g., ago(0,0,120,0,0,0) or ago(0,0,0,72,0,0).
Arguments:
years, in the range 0,1000
Years of run time. For convenience in conversion, a year of runtime is always 365 days (one year equals 31,536,000 seconds).
month, in the range 0,1000
Months of run time. For convenience in conversion, a month of runtime is always equal to 30 days of runtime (one month equals 2,592,000 seconds).
days, in the range 0,1000
Days of runtime (one day equals 86,400 seconds)
hours, in the range 0,1000
Hours of runtime
minutes, in the range 0,1000
Minutes of runtime 0-59
seconds, in the range 0,40000
Seconds of runtime
Example:
body common control
{
      bundlesequence => { "testbundle" };
}

bundle agent testbundle
{
  processes:

      ".*"

      process_count   => anyprocs,
      process_select  => proc_finder;

  reports:

    any_procs::

      "Found processes out of range";
}


body process_select proc_finder

{
      # Processes started between 100 years + 5.5 hours and 1 minute ago
      stime_range => irange(ago(100,0,0,5,30,0),ago(0,0,0,0,1,0));
      process_result => "stime";
}

body process_count anyprocs

{
      match_range => "0,0";
      out_of_range_define => { "any_procs" };
}
Output:
R: Found processes out of range
'''



'''
now
Table of Contents
Prototype: now()
Return type: int
Description: Return the time at which this agent run started in system representation.
In order to provide an immutable environment against which to converge, this value does not change during the execution of an agent.
Example:
    body file_select zero_age
    {
      mtime       => irange(ago(1,0,0,0,0,0),now);
      file_result => "mtime";
    }
'''



'''
strftime
Table of Contents
Prototype: strftime(mode, template, time)
Return type: string
Description: Interprets a time and date format string at a particular point in GMT or local time using Unix epoch time.
Arguments:
mode: one of
gmtime
localtime
template: string, in the range: .*
time: int, in the range: 0,99999999999
The mode is either gmtime (to get GMT times and dates) or localtime (to get times and dates according to the local timezone, usually specified by the TZ environment variable).
The conversion specifications that can appear in the format template are specialized for printing components of the date and time according to the system locale.
Example:
body common control
{
      bundlesequence => { "example" };
}

bundle agent example
{
  vars:
      "time" int => "1234567890";
      "at_time" string => strftime("localtime", "%Y-%m-%d %T", $(time));
      "then" string => strftime("localtime", "%Y-%m-%d %T", 0);

      "gmt_at_time" string => strftime("gmtime", "%Y-%m-%d %T", $(time));
      "gmt_then" string => strftime("gmtime", "%Y-%m-%d %T", 0);

  reports:
      # this will be different depending on your time zone
      # "time $(time); at_time $(at_time); then $(then)";

      # this will be the same in every time zone
      "time $(time); GMT at_time $(gmt_at_time); GMT then $(gmt_then)";
}
Output:
R: time 1234567890; GMT at_time 2009-02-13 23:31:30; GMT then 1970-01-01 00:00:00
Notes: Note that strftime is a standard C function and you should consult its reference to be sure of the specifiers it allows. The below is from the documentation of the standard strftime implementation in the glibc manual at http://www.gnu.org/software/libc/manual/html_node/Formatting-Calendar-Time.html#Formatting-Calendar-Time
Ordinary characters appearing in the template are copied to the output. Conversion specifiers are introduced by a % character and end with a format specifier taken from the following list. The whole % sequence is replaced in the output string as follows:
%a
The abbreviated weekday name according to the current locale.
%A
The full weekday name according to the current locale.
%b
The abbreviated month name according to the current locale.
%B
The full month name according to the current locale.
Using %B together with %d produces grammatically incorrect results for some locales.
%c
The preferred calendar time representation for the current locale.
%C
The century of the year. This is equivalent to the greatest integer not greater than the year divided by 100.
This format was first standardized by POSIX.2-1992 and by ISO C99.
%d
The day of the month as a decimal number (range 01 through 31).
%D
The date using the format %m/%d/%y.
This format was first standardized by POSIX.2-1992 and by ISO C99.
%e
The day of the month like with %d, but padded with blank (range 1 through 31).
This format was first standardized by POSIX.2-1992 and by ISO C99.
%F
The date using the format %Y-%m-%d. This is the form specified in the ISO 8601 standard and is the preferred form for all uses.
This format was first standardized by ISO C99 and by POSIX.1-2001.
%g
The year corresponding to the ISO week number, but without the century (range 00 through 99). This has the same format and value as %y, except that if the ISO week number (see %V) belongs to the previous or next year, that year is used instead.
This format was first standardized by ISO C99 and by POSIX.1-2001.
%G
The year corresponding to the ISO week number. This has the same format and value as %Y, except that if the ISO week number (see %V) belongs to the previous or next year, that year is used instead.
This format was first standardized by ISO C99 and by POSIX.1-2001 but was previously available as a GNU extension.
%h
The abbreviated month name according to the current locale. The action is the same as for %b.
This format was first standardized by POSIX.2-1992 and by ISO C99.
%H
The hour as a decimal number, using a 24-hour clock (range 00 through 23).
%I
The hour as a decimal number, using a 12-hour clock (range 01 through 12).
%j
The day of the year as a decimal number (range 001 through 366).
%k
The hour as a decimal number, using a 24-hour clock like %H, but padded with blank (range 0 through 23).
This format is a GNU extension.
%l
The hour as a decimal number, using a 12-hour clock like %I, but padded with blank (range 1 through 12).
This format is a GNU extension.
%m
The month as a decimal number (range 01 through 12).
%M
The minute as a decimal number (range 00 through 59).
%n
A single \n (newline) character.
This format was first standardized by POSIX.2-1992 and by ISO C99.
%p
Either AM or PM, according to the given time value; or the corresponding strings for the current locale. Noon is treated as PM and midnight as AM. In most locales AM/PM format is not supported, in such cases %p yields an empty string.
%P
Either am or pm, according to the given time value; or the corresponding strings for the current locale, printed in lowercase characters. Noon is treated as pm and midnight as am. In most locales AM/PM format is not supported, in such cases %P yields an empty string.
This format is a GNU extension.
%r
The complete calendar time using the AM/PM format of the current locale.
This format was first standardized by POSIX.2-1992 and by ISO C99. In the POSIX locale, this format is equivalent to %I:%M:%S %p.
%R
The hour and minute in decimal numbers using the format %H:%M.
This format was first standardized by ISO C99 and by POSIX.1-2001 but was previously available as a GNU extension.
%s
The number of seconds since the epoch, i.e., since 1970-01-01 00:00:00 UTC. Leap seconds are not counted unless leap second support is available.
This format is a GNU extension.
%S
The seconds as a decimal number (range 00 through 60).
%t
A single \t (tabulator) character.
This format was first standardized by POSIX.2-1992 and by ISO C99.
%T
The time of day using decimal numbers using the format %H:%M:%S.
This format was first standardized by POSIX.2-1992 and by ISO C99.
%u
The day of the week as a decimal number (range 1 through 7), Monday being 1.
This format was first standardized by POSIX.2-1992 and by ISO C99.
%U
The week number of the current year as a decimal number (range 00 through 53), starting with the first Sunday as the first day of the first week. Days preceding the first Sunday in the year are considered to be in week 00.
%V
The ISO 8601:1988 week number as a decimal number (range 01 through 53). ISO weeks start with Monday and end with Sunday. Week 01 of a year is the first week which has the majority of its days in that year; this is equivalent to the week containing the year's first Thursday, and it is also equivalent to the week containing January 4. Week 01 of a year can contain days from the previous year. The week before week 01 of a year is the last week (52 or 53) of the previous year even if it contains days from the new year.
This format was first standardized by POSIX.2-1992 and by ISO C99.
%w
The day of the week as a decimal number (range 0 through 6), Sunday being 0.
%W
The week number of the current year as a decimal number (range 00 through 53), starting with the first Monday as the first day of the first week. All days preceding the first Monday in the year are considered to be in week 00.
%x
The preferred date representation for the current locale.
%X
The preferred time of day representation for the current locale.
%y
The year without a century as a decimal number (range 00 through 99). This is equivalent to the year modulo 100.
%Y
The year as a decimal number, using the Gregorian calendar. Years before the year 1 are numbered 0, -1, and so on.
%z
RFC 822/*ISO 8601:1988* style numeric time zone (e.g., -0600 or +0100), or nothing if no time zone is determinable.
This format was first standardized by ISO C99 and by POSIX.1-2001 but was previously available as a GNU extension.
In the POSIX locale, a full RFC 822 timestamp is generated by the format %a, %d %b %Y %H:%M:%S %z (or the equivalent %a, %d %b %Y %T %z).
%Z
The time zone abbreviation (empty if the time zone can't be determined).
%%
A literal % character.
According to POSIX.1 every call to strftime checks the contents of the environment variable TZ before any output is produced.
'''