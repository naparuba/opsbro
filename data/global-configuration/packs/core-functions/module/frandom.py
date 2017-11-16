import random as random_lib
import copy

from opsbro.evaluater import export_evaluater_function

FUNCTION_GROUP = 'random'


@export_evaluater_function(function_group=FUNCTION_GROUP)
def random():
    """**random()** -> Returns a random float between 0 and 1

<code>
    Example:

        random()

    Returns:

        0.6988342144113194

</code>

    """
    return random_lib.random()


@export_evaluater_function(function_group=FUNCTION_GROUP)
def randomint_between(int_start, int_end):
    """**randomint_between(int_start, int_end)** -> Returns a random int between the start and the end

<code>
    Example:

        randomint_between(1, 100)

    Returns:

        69

</code>

    """
    return random_lib.randint(int_start, int_end)


@export_evaluater_function(function_group=FUNCTION_GROUP)
def shuffle(list):
    """**shuffle(list)** -> Return a copy of the list suffle randomly

<code>
    Example:

        suffle([ 1, 2, 3, 4 ])

    Returns:

        [ 3, 1, 4, 2 ]

</code>

    """
    # NOTE random.shuffle is in place
    n_list = copy.copy(list)
    random_lib.shuffle(n_list)
    return n_list
