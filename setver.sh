#!/bin/zsh
sed -i "s/^\(__version__ = \).*/\\1'${1}'/" **/*.py
