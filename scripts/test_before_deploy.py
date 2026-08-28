#!/usr/bin/env python3
import compileall,importlib,sys
if not compileall.compile_dir('backend',quiet=1): raise SystemExit('Ошибка компиляции backend/')
sys.path.insert(0,'backend')
for name in ['config','database','ai','ai_queue','ai_worker','admin_api','moderator_main','user_main']: importlib.import_module(name)
print('PRE-DEPLOY CHECK: OK')
