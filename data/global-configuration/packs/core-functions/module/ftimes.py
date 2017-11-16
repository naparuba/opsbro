import time
from opsbro.evaluater import export_evaluater_function

FUNCTION_GROUP = 'time'


@export_evaluater_function(function_group=FUNCTION_GROUP)
def now():
    """**now()** -> return the server system time as epoch (integer).

<code>
    Example:

        now()

    Returns:

        1510347324

</code>

    """
    return int(time.time())

