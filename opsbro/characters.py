# -*- coding: utf-8 -*-
import os


class Characters(object):
    # Box drawing
    vbar = u'│'
    hbar = u'─'
    hbar_light = u'─'
    corner_top_left = u'┌'
    corner_top_right = u'┐'
    corner_bottom_left = u'└'
    corner_bottom_right = u'┘'
    
    # Others
    hbar_dotted = u'᠁'
    vbar_dotted = u'⁞'
    
    # Ok or not
    check = u'√'
    cross = u'Х'
    double_exclamation = u'‼'
    
    # arrows
    arrow_left = u'→'
    arrow_double = u'↔'
    arrow_bottom = u'↓'
    arrow_top = u'↑'
    
    # Small numbers
    small_slash = u'̷'
    small_open = u'₍'
    small_0 = u'₀'
    small_1 = u'₁'
    small_2 = u'₂'
    small_3 = u'₃'
    small_4 = u'₄'
    small_5 = u'₅'
    small_6 = u'₆'
    small_7 = u'₇'
    small_8 = u'₈'
    small_9 = u'₉'
    small_close = u'₎'
    
    # Dots
    three_dots = u'…'
    
    # Topic display prefix
    topic_display_prefix = u'¦'
    topic_small_picto = u'▒'
    
    # Gun
    higer_gun = u'߹'
    middle_gun = u'█'
    lower_gun = u'߸'
    
    # Spinners
    spinners = u"⣷⣯⣟⡿⢿⣻⣽⣾"
    
    # Bar
    dot_bar = u'￭'
    bar_fill = u'█'
    bar_unfill = u'▒'


# Windows: don't know how to draw some characters, so fix them
if os.name == 'nt':
    # Box drawing
    # NOTE: if you have more heavy chars, I'm interested, because all I did found is ┏ but the vertical sign is not continue (space in putty at least)
    Characters.vbar = u'|'
    Characters.hbar = u'-'
    Characters.hbar_light = u'-'
    Characters.corner_top_left = u'*'
    Characters.corner_top_right = u'*'
    Characters.corner_bottom_left = u'*'
    Characters.corner_bottom_right = u'*'
    Characters.arrow_left = u'->'
    Characters.check = u'V'
    Characters.cross = u'X'
    Characters.double_exclamation = u'!!'
    Characters.spinners = u"⠁⠂⠄⡀⢀⠠⠐⠈"

CHARACTERS = Characters()

TEST_CHARS = u'➜ ❗️ ∎ ▁ ▂ ▃ ▄ ▅ ▆ ▇ █ ⬡ ⬢ ⬤ 🔥 √ 💬 ❗ 💦 ✅ Х → ↔ ↓ ↑ ‼ ៸ ⁄  ̷ ₍ 🎉 🎁 💰 👹 🔥 🌉 😍 🙌 📍 ✨ 🌟 ✨ ₀ ₁ ₂ ₃ ₄ ₅ ₆ ₇ ₈ ₉ ₎ ✔. ✓. ☐. ☑. ✗. ✘. ☐. ᠠᢩ  ┏ ┓ ━ ┗ ┛ ┃ ᠁ ᠉ ߺߺߺ ߹߹߹߹  ߸߸߸߸  ¯¯¯¯ ¦ ㉖ ✓ ✔ ✕ ✖ ✗ ✘ ➜ ➤ ✱ ❌ 𝖁 ❘ ᒧ ᒣ ᒪ ᒥ ¯ │ ⦁ ⌛ ⌦ ⏰ ☀ ☁ ★ ☕ ☢ ☹ ☺ ♚ ⚐ ⚒ ⚠ ⛅ ⛔ 😏 🍰 💬 📂 📤 📥 🔃 🔎 🔒 🔓 🔐 🔔 ⚛ ☠ ☢ ☣ ⚠ ⚡ ★ ☆ ⚝ ✩ ✪ ✫ ✬ ✭ 🆙  ☐ ☑ ☒ ⎗ ⎘ ⎌ ↶ ↷ ⟲ ⟳ ↺ ↻ 🔍 🔎 🔑 🔏 🔐 🔒 🔓 🌏 💣 🔨 🔧 🔩 ༼ ༽ ⎩ ⎧  ⎰ ⎱ ⎡ ⎣  ░░░▒▒▒▓▓▓███▓▓▒▒░░   ░░░▒▒▒▓▓▓███▓▓▒▒░░  ░░▒▒░▒▓███▓▒░ '
