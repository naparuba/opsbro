'''
ldaparray
Table of Contents
This function is only available in CFEngine Enterprise.
Prototype: ldaparray(array, uri, dn, filter, scope, security)
Return type: boolean
Description: Fills array with the entire LDAP record, and returns whether there was a match for the search.
This function retrieves an entire record with all elements and populates an associative array with the entries. It returns a class that is true if there was a match for the search, and false if nothing was retrieved.
Arguments:
array: string, in the range: .*
uri: string, in the range: .*
dn: string, in the range: .*
filter: string, in the range: .*
scope: one of
subtree
onelevel
base
security: one of
none
ssl
sasl
dn specifies the distinguished name, an ldap formatted name built from components, e.g. "dc=cfengine,dc=com". filter is an ldap search, e.g. "(sn=User)". Which security values are supported depends on machine and server capabilities.
Example:
classes:

   "gotdata" expression => ldaparray(
                                    "myarray",
                                    "ldap://ldap.example.org",
                                    "dc=cfengine,dc=com",
                                    "(uid=mark)",
                                    "subtree",
                                    "none");
'''



'''
ldapvalue
Table of Contents
This function is only available in CFEngine Enterprise.
Prototype: ldapvalue(uri, dn, filter, record, scope, security)
Return type: string
The return value is cached.
Description: Returns the first matching named value from ldap.
This function retrieves a single field from a single LDAP record identified by the search parameters. The first matching value it taken.
Arguments:
uri: string, in the range: .*
dn: string, in the range: .*
filter: string, in the range: .*
record: string, in the range: .*
scope: one of
subtree
onelevel
base
security: one of
none
ssl
sasl
dn specifies the distinguished name, an ldap formatted name built from components, e.g. "dc=cfengine,dc=com". filter is an ldap search, e.g. "(sn=User)", and record is the name of the single record to be retrieved, e.g. uid. Which security values are supported depends on machine and server capabilities.
Example:
vars:

   # Get the first matching value for "uid" in schema

  "value" string => ldapvalue(
                             "ldap://ldap.example.org",
                             "dc=cfengine,dc=com",
                             "(sn=User)",
                             "uid",
                             "subtree",
                             "none"
                             );
'''



'''
ldaplist
Table of Contents
This function is only available in CFEngine Enterprise.
Prototype: ldaplist(uri, dn, filter, record, scope, security)
Return type: slist
The return value is cached.
Description: Returns a list with all named values from multiple ldap records.
This function retrieves a single field from all matching LDAP records identified by the search parameters.
Arguments:
uri: string, in the range: .*
dn: string, in the range: .*
filter: string, in the range: .*
record: string, in the range: .*
scope: one of
subtree
onelevel
base
security: one of
none
ssl
sasl
dn specifies the distinguished name, an ldap formatted name built from components, e.g. "dc=cfengine,dc=com". filter is an ldap search, e.g. "(sn=User)", and record is the name of the single record to be retrieved, e.g. uid. Which security values are supported depends on machine and server capabilities.
Example:
vars:

   # Get all matching values for "uid" - should be a single record match

  "list" slist =>  ldaplist(
                           "ldap://ldap.example.org",
                           "dc=cfengine,dc=com",
                           "(sn=User)",
                           "uid",
                           "subtree",
                           "none"
                           );

'''


'''
regldap
Table of Contents
This function is only available in CFEngine Enterprise.
Prototype: regldap(uri, dn, filter, record, scope, regex, security)
Return type: boolean
The return value is cached.
Description: Returns whether the regular expression regex matches a value item in the LDAP search.
This function retrieves a single field from all matching LDAP records identified by the search parameters and compares it to the regular expression regex.
Arguments:
uri: string, in the range: .*
dn: string, in the range: .*
filter: string, in the range: .*
record: string, in the range: .*
scope: one of
subtree
onelevel
base
regex: regular expression, in the range: .*
security: one of
none
ssl
sasl
dn specifies the distinguished name, an ldap formatted name built from components, e.g. "dc=cfengine,dc=com". filter is an ldap search, e.g. "(sn=User)", and record is the name of the single record to be retrieved and matched against regex, e.g. uid. Which security values are supported depends on machine and server capabilities.
Example:
classes:

   "found" expression => regldap(
                                "ldap://ldap.example.org",
                                "dc=cfengine,dc=com",
                                "(sn=User)",
                                "uid",
                                "subtree",
                                "jon.*",
                                "none"
                                );
'''