#!/usr/bin/zsh
autoload -U zfinit
zfinit
rm dist/*
pysdist
export EMAIL_ADDR="a.schmolck@gmx.net"
zfanon upload.sf.net
zfcd incoming
zfput dist/*
