# -*- coding: utf-8 -*-
"""验证 Flask 应用能否正常启动"""

import sys
sys.path.insert(0, '.')

print('=== Testing Flask Application After Migration ===')
print('')

try:
    from app.application import app
    print('[OK] Flask app imported successfully')

    print('')
    print('Registered Blueprints:')
    for bp_name, bp in app.blueprints.items():
        prefix = bp.url_prefix if hasattr(bp, 'url_prefix') and bp.url_prefix else '/'
        print(f'  - {bp_name}: {prefix}')

    print('')
    print('Key API Routes:')
    routes = []
    for rule in app.url_map.iter_rules():
        if 'api' in rule.rule or 'auto_test' in rule.rule:
            methods = list(rule.methods - {'HEAD', 'OPTIONS'})
            routes.append(f'{rule.rule} {methods}')

    for r in sorted(routes)[:20]:
        print(f'  {r}')

    print('')
    print('[OK] Flask application is ready after migration!')
except Exception as e:
    print(f'[FAIL] Flask app: {e}')
    import traceback
    traceback.print_exc()
