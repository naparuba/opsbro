COLOR_PACK_LIGHT_GREEN_TO_DARK_PURPLE = 1
# lower (light green=59) to max (dark purple=28)
DARK_PURPLE = 28
LIGHT_GREEN = 59

COLOR_PACK_CITRON_TO_VIOLET = 2
CITRON = 0
VIOLET = 28


class ColorPalette(object):
    @staticmethod
    def get_color_from_percent_between_0_1(pct, color_pack=COLOR_PACK_LIGHT_GREEN_TO_DARK_PURPLE):
        if color_pack == COLOR_PACK_LIGHT_GREEN_TO_DARK_PURPLE:
            COLOR_START = DARK_PURPLE
            COLOR_END = LIGHT_GREEN
        elif color_pack == COLOR_PACK_CITRON_TO_VIOLET:
            COLOR_START = CITRON
            COLOR_END = VIOLET
        else:
            raise Exception('Bad color pack %s' % color_pack)
        # get a degraded color
        color_range = COLOR_END - COLOR_START
        color = COLOR_START + (pct * color_range)
        return int(color)


colorpalette = ColorPalette()
