#!/bin/bash

source venv/bin/activate

python3 setup.py py2app

rm -rf dmg
mkdir dmg

hdiutil create dmg/temp.dmg -ov -volname "GitSyncBar" -fs HFS+ -srcfolder "./dist"
hdiutil convert dmg/temp.dmg -format UDZO -o dmg/GitSyncBar.dmg

rm dmg/temp.dmg