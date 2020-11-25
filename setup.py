from setuptools import setup

APP = ['a2.py']
DATA_FILES = ['config.json']
OPTIONS = {
	'argv_emulation': True,
	'iconfile':'icon.icns',
	'plist':{
		'LSUIElement': True,
		'CFBundleIdentifier':'net.quikstorm.gitsyncbar',
		'CFBundleShortVersionString':'0.0.1',
	},
	'packages': ['rumps', 'watchdog']
}

setup(
	app=APP,
	name='GitSyncBar',
	data_files=DATA_FILES,
	options={'py2app':OPTIONS},
	setup_requires=['py2app'],
)