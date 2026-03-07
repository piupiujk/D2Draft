"""Обработка текстовых кнопок главного меню: роутинг reply-клавиатуры.

Кнопки, для которых уже есть полноценные хендлеры (BTN_META, BTN_BUILD,
BTN_MATCH, BTN_PROFILE, BTN_SETTINGS, BTN_DRAFT), обрабатываются
в соответствующих модулях (meta.py, build.py, match.py, profile.py,
settings.py, draft.py).

Этот модуль пуст — все кнопки главного меню обработаны в своих роутерах.
"""

from __future__ import annotations

from aiogram import Router

router = Router(name="menu")
