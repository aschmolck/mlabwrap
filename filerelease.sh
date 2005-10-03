#!/usr/bin/zsh
rm dist/*
pysdist
zfanon upload.sf.net
zfcd incoming
zfput dist/*
