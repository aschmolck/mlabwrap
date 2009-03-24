#!/bin/bash
rst2html README.txt --stylesheet=Steely.css index.html
[[ -z $1 ]] && exit 0;
ssh aschmolck,mlabwrap@shell.sourceforge.net create && \
scp index.html *.css *..png aschmolck@shell.sf.net:/home/groups/m/ml/mlabwrap/htdocs/

