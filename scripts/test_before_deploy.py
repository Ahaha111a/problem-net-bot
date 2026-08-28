#!/usr/bin/env python3
"""Минимальный pre-deploy smoke test: импорт модулей + компиляция."""
import compileall
import importlib
import sys

if not compileall.compile_dir('backend', quiet=1):
    raise SystemExit('Ошибка компиляции Python-файлов backend/')

modules = ['backend.database', 'backend.ai', 'backend.admin_api', 'backend.moderator_main', 'backend.user_main']
for name in modules:
    importlib.import_module(name)
print('PRE-DEPLOY CHECK: OK')
