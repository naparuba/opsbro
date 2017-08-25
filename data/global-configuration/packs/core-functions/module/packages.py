from opsbro.evaluater import export_evaluater_function
from opsbro.systempacketmanager import systepacketmgr


@export_evaluater_function
def has_package(package):
    """**has_package(package)** -> return True if the package is installed on the system, False otherwise.

 * package: (string) name of the package to check for.

<code>
    Example:
        has_package('postfix')
    Returns:
        False
</code>
    """
    return systepacketmgr.has_package(package)
