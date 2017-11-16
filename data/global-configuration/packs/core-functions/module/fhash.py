from opsbro.evaluater import export_evaluater_function

FUNCTION_GROUP = 'hash'


def _do_hash(string, algorithm):
    import hashlib
    f = {'md5': hashlib.md5, 'sha1': hashlib.sha1, 'sha224': hashlib.sha224, 'sha256': hashlib.sha256, 'sha384': hashlib.sha384, 'sha512': hashlib.sha512}.get(algorithm, None)
    if f is None:
        raise Exception('hash:: algorithm %s is unknown' % algorithm)
    return f(string).hexdigest()


@export_evaluater_function(function_group=FUNCTION_GROUP)
def hash(string, algorithm):
    """**hash(string, algorithm)** -> Returns a hash of the string with the algorithm in:
 * md5
 * sha1
 * sha224
 * sha256
 * sha384
 * sha512

<code>
    Example:

        hash('I want to hash', 'sha1')

    Returns:

        '1eec44fd0443a3a9138d7b0f6c027bd0ed3c59b7'

</code>

    """
    return _do_hash(string, algorithm)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def file_hash_match(path, algorithm, hash_match):
    """**file_hash_match(path, algorithm, hash_match)** -> Returns True if the hash of the file at path is equal to hash_match.
Available algorithms:

 * md5
 * sha1
 * sha224
 * sha256
 * sha384
 * sha512

<code>
    Example:

        file_hash_match('/etc/passwd', 'md5', '1eec44fd0443a3a9138d7b0f6c027bd0ed3c59b7')

    Returns:

        False

</code>

    """
    with open(path, 'rb') as f:
        string = f.read()
        file_hash = _do_hash(string, algorithm)
    return file_hash == hash_match
