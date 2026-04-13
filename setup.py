from setuptools import setup

APP = ['screenshot_app.py']
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'LSUIElement': True,
        'CFBundleName': 'SnapDraw',
    },
    'packages': ['rumps', 'PIL'],
}

setup(
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)