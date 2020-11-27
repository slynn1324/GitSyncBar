#!/bin/bash

set -e 


source venv/bin/activate

# clean
rm -rf dmg build dist

python3 setup.py py2app

mkdir dmg

hdiutil create dmg/temp.dmg -ov -volname "GitSyncBar" -fs HFS+ -srcfolder "./dist"
hdiutil convert dmg/temp.dmg -format UDZO -o dmg/GitSyncBar.dmg

rm dmg/temp.dmg
