# -*- coding: utf-8 -*-
#

# LGPL, cf dashing-LICENCE
# From https://github.com/FedericoCeratto/dashing
from __future__ import print_function
import time
import sys
from collections import deque, namedtuple
import copy

try:
    unichr
except NameError:
    unichr = chr

from opsbro.cli_display import DonutPrinter, get_terminal_size, HBarPrinter
from opsbro.misc.lolcat import lolcat
from opsbro.info import TITLE_COLOR
from opsbro.misc.bro_quotes import get_quote
from opsbro.colorpalette import colorpalette
from opsbro.characters import CHARACTERS
from opsbro.util import PY3

if PY3:
    basestring = str

# "graphic" elements

border_bl = CHARACTERS.corner_bottom_left  # u'└'
border_br = CHARACTERS.corner_bottom_right  # u'┘'
border_tl = CHARACTERS.corner_top_left  # u'┌'
border_tr = CHARACTERS.corner_top_right  # u'┐'
border_h = CHARACTERS.hbar  # u'─'
border_v = CHARACTERS.vbar  # u'│'
# hbar_elements = (u"▏", u"▎", u"▍", u"▌", u"▋", u"▊", u"▉")
# vbar_elements = (u"▁", u"▂", u"▃", u"▄", u"▅", u"▆", u"▇", u"█")
# braille_left = (0x01, 0x02, 0x04, 0x40, 0)
# braille_right = (0x08, 0x10, 0x20, 0x80, 0)
braille_r_left = (0x04, 0x02, 0x01)
braille_r_right = (0x20, 0x10, 0x08)

TBox = namedtuple('TBox', 'x y w h')

from opsbro.log import cprint


def LOG(s):
    f = open('/tmp/log.txt', 'a')
    f.write(s + '\n')
    f.close()


class Tile(object):
    def __init__(self, title=None, border_color=None, color=0, max_height=None, id='', vcallback=None, unit=''):
        self.title = title
        self.color = color
        self.border_color = border_color
        self.max_height = max_height
        self.id = id
        self.vcallback = vcallback
        self.unit = unit
        
        self._got_value = False  # protect for display before get data
    
    
    def __str__(self):
        return ' %s(id=%s, title=%s) ' % (type(self), self.id, self.title)
    
    
    def _get_size(self):
        return None, self.max_height
    
    
    def display(self, tbox, parent):
        if not self._got_value:
            self.refresh_value()
        self._display(tbox, parent)
    
    
    def _display(self, tbox, parent):
        """Render current tile
        """
        raise NotImplementedError
    
    
    def refresh_value(self):
        self._refresh_value()
        self._got_value = True
    
    
    def _refresh_value(self):
        raise NotImplementedError
    
    
    # Go to the position x,y of the terminal
    # NOTE: +1 because the position are starting at 1, not 0
    def _jump_to(self, x, y):
        cprint(u'\033[%d;%dH' % (x + 1, y + 1), end='')
    
    
    def _draw_borders(self, tbox):
        # top border
        self._jump_to(tbox.x, tbox.y)
        cprint(border_tl + border_h * (tbox.w - 2) + border_tr, color='cyan', end='')
        
        # left and right
        for dx in range(1, tbox.h - 1):
            self._jump_to(tbox.x + dx, tbox.y)
            cprint(border_v, color='cyan', end='')
            
            self._jump_to(tbox.x + dx, tbox.y + tbox.w - 1)
            cprint(border_v, color='cyan', end='')
        # bottom
        self._jump_to(tbox.x + tbox.h - 1, tbox.y)
        cprint(border_bl + border_h * (tbox.w - 2) + border_br, color='cyan', end='')
    
    
    def _draw_borders_and_title(self, tbox):
        """Draw borders and title as needed and returns
        inset (x, y, width, height)
        """
        if self.border_color is not None:
            self._draw_borders(tbox)
        
        if self.title:
            fill_all_width = (self.border_color is None)
            self._draw_title(tbox, fill_all_width)
        
        if self.border_color is not None:
            return TBox(tbox.x + 1, tbox.y + 1, tbox.w - 2, tbox.h - 2)
        
        elif self.title is not None:
            return TBox(tbox.x + 1, tbox.y, tbox.w - 1, tbox.h - 1)
        
        return TBox(tbox.x, tbox.y, tbox.w, tbox.h)
    
    
    def full_display(self, title):
        try:
            terminal_height, terminal_width = get_terminal_size()
        except:  # maybe in a stransge shell
            terminal_width = terminal_height = 100
        
        # Clear the terminal
        cprint('\033c')
        
        tbox = TBox(1, 0, terminal_width, terminal_height - 2)  # -1 for title, -1 for the ending line
        
        # Show the title at the first line
        self._jump_to(0, 0)
        
        # Put OpsBro title on all dashboards
        cprint(u' %s' % TITLE_COLOR, end='')
        
        # Put the title in the middle of the first line
        title = u'ʃ %s ʅ' % title
        l_title = len(title)
        title = lolcat.get_line(title, 1, spread=1)
        self._jump_to(0, int((terminal_width / 2) - (l_title / 2)))
        cprint(title, end='')
        
        time_format = time.strftime("%H:%M")
        self._jump_to(0, terminal_width - len(time_format) - 1)
        cprint(time_format, color='white', end='')
        
        # Now display the other box
        self.display(tbox, None)
        
        self._jump_to(terminal_height - 1, 0)
        cprint(' http://opsbro.io (by Shinken Solutions team)', color='grey', end='')
        
        quote, from_film = get_quote()
        full_quote = '>> %s  (%s)' % (quote, from_film)
        l_full_quote = len(full_quote)
        self._jump_to(terminal_height - 1, terminal_width - l_full_quote)
        cprint(full_quote, color='grey', end='')
        
        # park cursor in a safe place and reset color
        self._jump_to(terminal_height, -1)
        sys.stdout.flush()
    
    
    def _draw_title(self, tbox, fill_all_width):
        if not self.title:
            return
        margin = int((tbox.w - len(self.title)) / 20)
        if fill_all_width:
            title = ' ' * margin + self.title + ' ' * (tbox.w - margin - len(self.title))
            
            self._jump_to(tbox.x, tbox.y)
            cprint(title, on_color='on_grey', end='')
        else:
            title = ' ' * margin + self.title + ' ' * margin
            
            self._jump_to(tbox.x, tbox.y + margin)
            cprint(title, on_color='on_grey', end='')


class Split(Tile):
    def __init__(self, *items, **kw):
        super(Split, self).__init__(**kw)
        self.items = items
        
        self._update_value_lock = None  # do not want to lock for such objects
    
    
    # For vertical: get the max of our items as our max height
    def _get_size(self):
        if len(self.items) == 0:
            return None, None
        max_height = None
        items_with_max_height = []
        items_without_max_height = []
        for i in self.items:
            max_width, max_height = i._get_size()
            if max_height:
                items_with_max_height.append(i)
            else:
                items_without_max_height.append(i)
        
        # If only with size, take max it
        if len(items_without_max_height) == 0:
            max_height = 0
            for i in items_with_max_height:
                i_w, i_h = i._get_size()
                max_height = max(max_height, i_h)
            return None, max_height
        
        return None, None
    
    
    def _display(self, tbox, parent):
        """Render current tile and its items. Recurse into nested splits
        """
        tbox = self._draw_borders_and_title(tbox)
        
        if not self.items:
            # empty split
            return
        LOG('*******')
        LOG('myself %s sons are %s' % (self, self.items))
        LOG('TBOX H %s  is %d' % (self, tbox.h))
        
        reserved_height = 0
        items_with_max_height = []
        items_without_max_height = []
        for i in self.items:
            max_width, max_height = i._get_size()
            if max_height:
                items_with_max_height.append(i)
                reserved_height += max_height + 2  # 2 for top/bottom border
            else:
                items_without_max_height.append(i)
        LOG("Box hight: %d  reserved height: %d" % (tbox.h, reserved_height))
        if isinstance(self, VSplit):
            if items_without_max_height:
                item_height = (tbox.h - reserved_height) // len(items_without_max_height)
            else:
                item_height = 0
            item_width = tbox.w
        else:
            item_height = tbox.h
            item_width = tbox.w // len(self.items)
        
        x = tbox.x
        y = tbox.y
        for i in self.items:
            max_width, max_height = i._get_size()
            LOG('  ITEM: %s height=%s' % (i, max_height))
            if max_height is None:
                max_height = item_height
            else:
                max_height += 2  # count the border too
            LOG("DISPLAY %s %s %s %s" % (type(i), max_height, 'will display at addr', x))
            i.display(TBox(x, y, item_width, max_height), self)
            if isinstance(self, VSplit):
                x += max_height
            else:
                y += item_width
    
    
    # Do not want the lock for such objects
    def refresh_value(self):
        for i in self.items:
            i.refresh_value()


class VSplit(Split):
    pass


class HSplit(Split):
    pass


class Text(Tile):
    def __init__(self, text, color=2, *args, **kw):
        super(Text, self).__init__(**kw)
        self.text = text
        self.color = color
    
    
    # Take automatically the size of the text in height
    def _get_size(self):
        return None, len(self.text.splitlines())
    
    
    def _refresh_value(self):
        if self.vcallback is None:
            return
        
        text = self.vcallback()
        if text is None:
            text = ''
        self.text = text
    
    
    def _display(self, tbox, parent):
        tbox = self._draw_borders_and_title(tbox)
        
        dx = 0
        for dx, line in enumerate(self.text.splitlines()):
            self._jump_to(tbox.x + dx, tbox.y)
            cprint(line + ' ' * (tbox.w - len(line)), color='white', end='')
        dx += 1
        while dx < tbox.h:
            self._jump_to(tbox.x + dx, tbox.y)
            cprint(' ' * tbox.w, end='')
            dx += 1


'''
class Log(Tile):
    def __init__(self, *args, **kw):
        self.logs = deque(maxlen=50)
        super(Log, self).__init__(**kw)
    
    
    def _display(self, tbox, parent):
        tbox = self._draw_borders_and_title(tbox)
        n_logs = len(self.logs)
        log_range = min(n_logs, tbox.h)
        start = n_logs - log_range
        
        i = 0
        for i in range(0, log_range):
            line = self.logs[start + i]
            print(tbox.t.move(tbox.x + i, tbox.y) + line + ' ' * (tbox.w - len(line)))
        
        if i < tbox.h:
            for i2 in range(i + 1, tbox.h):
                print(tbox.t.move(tbox.x + i2, tbox.y) + ' ' * tbox.w)
    
    
    def append(self, msg):
        self.logs.append(msg)
'''


class HGauge(Tile):
    def __init__(self, label='', title='', val=100, color=2, **kw):
        kw['color'] = color
        kw['title'] = title
        super(HGauge, self).__init__(**kw)
        self.value = val
        self.label_orig = label if label else ''
        self.title_orig = title if title else ''
        self.max_height = 1
        self.label = ''
    
    
    def _refresh_value(self):
        if self.vcallback is None:
            return
        value = self.vcallback()
        if value is None:
            value = 0
        if isinstance(value, basestring):
            try:
                value = int(value)
            except ValueError:
                value = 0
        self.value = value
    
    
    def _display(self, tbox, parent):
        self.title = self.title_orig + (': %d %s' % (self.value, self.unit))
        tbox = self._draw_borders_and_title(tbox)
        self._jump_to(tbox.x, tbox.y)
        
        value_ratio = max(0, min(1, self.value / 100.0))
        
        bar = HBarPrinter().get_hbar(value_ratio, tbox.w)
        cprint(bar, end='')


'''
class VGauge(Tile):
    def __init__(self, val=100, color=2, **kw):
        kw['color'] = color
        super(VGauge, self).__init__(**kw)
        self.value = val
        self.max_height = 5
    
    
    def _refresh_value(self):
        if self.vcallback is None:
            return
        value = self.vcallback()
        if value is None:
            value = 0
        self.value = value
    
    def _display(self, tbox, parent):
        """Render current tile
        """
        tbox = self._draw_borders_and_title(tbox)
        nh = tbox.h * (self.value / 100.5)
        print(tbox.t.move(tbox.x, tbox.y) + tbox.t.color(self.color))
        for dx in range(tbox.h):
            m = tbox.t.move(tbox.x + tbox.h - dx - 1, tbox.y)
            if dx < int(nh):
                bar = vbar_elements[-1] * tbox.w
            elif dx == int(nh):
                index = int((nh - int(nh)) * 8)
                bar = vbar_elements[index] * tbox.w
            else:
                bar = ' ' * tbox.w
            
            print(m + bar)
'''


class VDonut(Tile):
    def __init__(self, val=66, title='', color=2, label='', **kw):
        kw['color'] = color
        kw['title'] = title
        
        super(VDonut, self).__init__(**kw)
        self.label = label
        self.value = val
        self.max_height = 7  # 6 for donut, 1 for the label
        self.title_orig = title
    
    
    def _refresh_value(self):
        if self.vcallback is None:
            return
        
        value = self.vcallback()
        if value is None:
            value = 0
        if value < 0:
            value = 0
        if value > 100:
            value = 0
        self.value = value
    
    
    def _display(self, tbox, parent):
        self.title = self.title_orig + (': %d %s' % (self.value, self.unit))
        tbox = self._draw_borders_and_title(tbox)
        
        donut_s = DonutPrinter().get_donut(self.value)
        logs = donut_s.splitlines()
        logs.append(self.label)
        n_logs = len(logs)
        log_range = min(n_logs, tbox.h)
        start = n_logs - log_range
        
        for i in range(0, log_range):
            line = logs[start + i]
            self._jump_to(tbox.x + i, tbox.y)
            cprint(line + ' ' * (tbox.w - len(line)), end='')


'''
class ColorRangeVGauge(Tile):
    """Vertical gauge with color map.
    E.g.: green gauge for values below 50, red otherwise:
    colormap=((50, 2), (100, 1))
    """
    
    
    def __init__(self, val=100, colormap=(), **kw):
        self.colormap = colormap
        super(ColorRangeVGauge, self).__init__(**kw)
        self.value = val
    
    
    def _display(self, tbox, parent):
        tbox = self._draw_borders_and_title(tbox)
        nh = tbox.h * (self.value / 100.5)
        filled_element = vbar_elements[-1]
        for thresh, col in self.colormap:
            if thresh > self.value:
                break
        print(tbox.t.move(tbox.x, tbox.y) + tbox.t.color(col))
        for dx in range(tbox.h):
            m = tbox.t.move(tbox.x + tbox.h - dx - 1, tbox.y)
            if dx < int(nh):
                bar = filled_element * tbox.w
            elif dx == int(nh):
                index = int((nh - int(nh)) * 8)
                bar = vbar_elements[index] * tbox.w
            else:
                bar = ' ' * tbox.w
            
            print(m + bar)
'''

'''
class VChart(Tile):
    """Vertical chart. Values must be between 0 and 100 and can be float.
    """
    
    
    def __init__(self, val=100, *args, **kw):
        super(VChart, self).__init__(**kw)
        self.value = val
        self.datapoints = deque(maxlen=50)
    
    
    def append(self, dp):
        self.datapoints.append(dp)
    
    
    def _display(self, tbox, parent):
        tbox = self._draw_borders_and_title(tbox)
        filled_element = hbar_elements[-1]
        scale = tbox.w / 100.0
        print(tbox.t.color(self.color))
        for dx in range(tbox.h):
            index = 50 - (tbox.h) + dx
            try:
                dp = self.datapoints[index] * scale
                index = int((dp - int(dp)) * 8)
                bar = filled_element * int(dp) + hbar_elements[index]
                assert len(bar) <= tbox.w, dp
                bar += ' ' * (tbox.w - len(bar))
            except IndexError:
                bar = ' ' * tbox.w
            print(tbox.t.move(tbox.x + dx, tbox.y) + bar)
'''

'''
class HChart(Tile):
    """Horizontal chart, filled
    """
    
    
    def __init__(self, val=100, *args, **kw):
        super(HChart, self).__init__(**kw)
        self.value = val
        self.datapoints = deque(maxlen=500)
    
    
    def append(self, dp):
        self.datapoints.append(dp)
    
    
    def _refresh_value(self):
        if self.vcallback is None:
            return
        
        value = self.vcallback()
        if value is None:
            value = 0
        self.append(value)
    
    
    def _display(self, tbox, parent):
        tbox = self._draw_borders_and_title(tbox)
        print(tbox.t.color(self.color))
        for dx in range(tbox.h):
            bar = ''
            for dy in range(tbox.w):
                dp_index = - tbox.w + dy
                try:
                    dp = self.datapoints[dp_index]
                    q = (1 - dp / 100) * tbox.h
                    if dx == int(q):
                        index = int((int(q) - q) * 8 - 1)
                        bar += vbar_elements[index]
                    elif dx < int(q):
                        bar += ' '
                    else:
                        bar += vbar_elements[-1]
                
                except IndexError:
                    bar += ' '
            
            # assert len(bar) == tbox.w
            print(tbox.t.move(tbox.x + dx, tbox.y) + bar)
'''

'''
class HBrailleChart(Tile):
    def __init__(self, val=100, *args, **kw):
        super(HBrailleChart, self).__init__(**kw)
        self.value = val
        self.datapoints = deque(maxlen=500)
    
    
    def append(self, dp):
        self.datapoints.append(dp)
    
    
    def _refresh_value(self):
        if self.vcallback is None:
            return
        
        self.value = self.vcallback()
        if self.value is None:
            self.value = 0
        self.append(self.value)
    
    
    def _generate_braille(self, l, r):
        v = 0x28 * 256 + (braille_left[l] + braille_right[r])
        return unichr(v)
    
    
    def _display(self, tbox, parent):
        tbox = self._draw_borders_and_title(tbox)
        
        print(tbox.t.color(self.color))
        for dx in range(tbox.h):
            bar = ''
            for dy in range(tbox.w):
                dp_index = (dy - tbox.w) * 2
                try:
                    dp1 = self.datapoints[dp_index]
                    dp2 = self.datapoints[dp_index + 1]
                except IndexError:
                    # no data (yet)
                    bar += ' '
                    continue
                
                q1 = (1 - dp1 / 100) * tbox.h
                q2 = (1 - dp2 / 100) * tbox.h
                if dx == int(q1):
                    index1 = int((q1 - int(q1)) * 4)
                    if dx == int(q2):  # both datapoints in the same rune
                        index2 = int((q2 - int(q2)) * 4)
                    else:
                        index2 = -1  # no dot
                    bar += self._generate_braille(index1, index2)
                elif dx == int(q2):
                    # the right dot only is in the current rune
                    index2 = int((q2 - int(q2)) * 4)
                    bar += self._generate_braille(-1, index2)
                else:
                    bar += ' '
            
            print(tbox.t.move(tbox.x + dx, tbox.y) + bar)
'''


class HBrailleFilledChart(Tile):
    def __init__(self, val=100, title='', *args, **kw):
        kw['title'] = title
        super(HBrailleFilledChart, self).__init__(**kw)
        self.value = val
        self.datapoints = deque(maxlen=500)
        self.title_orig = title
    
    
    def append(self, dp):
        # IMPORTANT: we must be lock free, so work with a copy
        new_datapoints = copy.copy(self.datapoints)
        new_datapoints.append(dp)
        self.datapoints = new_datapoints
    
    
    def _refresh_value(self):
        if self.vcallback is None:
            return
        
        value = self.vcallback()
        if value is None:
            value = 0
        # If percent, max to 0=>100
        if self.unit == '%':
            value = min(100, max(0, value))
        self.value = value
        self.append(value)
    
    
    def _generate_braille(self, lmax, rmax):
        v = 0x28 * 256
        for l in range(lmax):
            v += braille_r_left[l]
        for r in range(rmax):
            v += braille_r_right[r]
        return unichr(v)
    
    
    def _get_braille_idx_from_pos(self, y_value, line_idx):
        if line_idx == int(y_value):  # 1/4=>3/4 height
            index = 3 - int((y_value - int(y_value)) * 4)
        elif line_idx > y_value:  # full
            index = 3
        else:
            index = 0
        return index
    
    
    def _display(self, tbox, parent):
        self.title = self.title_orig + (': %d %s' % (self.value, self.unit))
        
        tbox = self._draw_borders_and_title(tbox)
        
        box_height = tbox.h
        box_width = tbox.w
        
        for line_idx in range(box_height):
            # get a degraded color, wil be the same for all the line
            pct = 1.0 * line_idx / box_height
            line_color = colorpalette.get_color_from_percent_between_0_1(pct)
            bar = ''
            for col_idx in range(box_width):
                dp_index = (col_idx - box_width) * 2
                try:
                    value_1 = self.datapoints[dp_index]
                    value_2 = self.datapoints[dp_index + 1]
                except IndexError:
                    # no data (yet)
                    # and no color too, useful for quick debug by hightlight shell :)
                    bar += ' '
                    continue
                # TODO: manage more than % here, with min/max
                v1_ratio = value_1 / 100.0
                v2_ratio = value_2 / 100.0
                y_v1 = (1 - v1_ratio) * box_height
                y_v2 = (1 - v2_ratio) * box_height
                index1 = self._get_braille_idx_from_pos(y_v1, line_idx)
                index2 = self._get_braille_idx_from_pos(y_v2, line_idx)
                
                char = self._generate_braille(index1, index2)
                
                color_char = lolcat.get_line(char, line_color, spread=None)
                bar += color_char
            
            self._jump_to(tbox.x + line_idx, tbox.y)
            cprint(bar, end='')
