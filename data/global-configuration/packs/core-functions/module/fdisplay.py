# -*- coding: utf-8 -*-

from opsbro.evaluater import export_evaluater_function

FUNCTION_GROUP = 'display'


@export_evaluater_function(function_group=FUNCTION_GROUP)
def get_donut(value):
    u"""**get_donut(value)** -> return a string a chart donut

 * value: int or float of the integer value to print

<code>
    Example:
        get_donut(14)
    Returns:
  ⢀⣤⣶⣿⣿⣿⣷⣦⣄
 ⢰⣿⣿⣿⠿⠛⠻⢿⣿⣿⣷
 ⣿⣿⣿⠃ 14 ⢻⣿⣿⡇
 ⢿⣿⣿⣆ % ⢀⣾⣿⣿⠇
 ⠘⢿⣿⣿⣿⣶⣾⣿⣿⣿⠟
   ⠙⠿⣿⣿⣿⡿⠟⠁
</code>
    """
    from opsbro.cli_display import DonutPrinter
    donut_string = DonutPrinter().get_donut(value)
    return donut_string
