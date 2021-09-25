#!/bin/bash
set -eu

DISTDIR=dist/axium-1.0.0
mkdir -p $DISTDIR
cat requirements.txt wasabi2d/requirements.txt >$DISTDIR/requirements.txt
cp -a *.py README.md $DISTDIR
cp -a images music data fonts sounds $DISTDIR
cp -a wasabi2d/wasabi2d $DISTDIR

find $DISTDIR -name __pycache__ -print0 | xargs -0 rm -rf

ZIPPATH="$(dirname "${DISTDIR}")"
ZIPNAME="$(basename "${DISTDIR}")"
( cd $ZIPPATH && zip -ur "${ZIPNAME}.zip" "$ZIPNAME" )
rm -rf "${DISTDIR}"
