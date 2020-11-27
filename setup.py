from setuptools import setup

APP = ['app.py']
DATA_FILES = ['icon.pdf', 'icon-sync.pdf', 'icon-exclamation.pdf', 'icon-50pct.png']
OPTIONS = {
	'argv_emulation': True,
	'iconfile':'icon.icns',
	'plist':{
		'LSUIElement': True,
		'CFBundleIdentifier':'net.quikstorm.gitsyncbar',
		'CFBundleShortVersionString':'0.0.4',
	},
	'packages': ['rumps']
}

setup(
	app=APP,
	name='GitSyncBar',
	data_files=DATA_FILES,
	options={'py2app':OPTIONS},
	setup_requires=['py2app'],
)
