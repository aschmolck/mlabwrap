#!/bin/bash
sfuser=${sfuser:-aschmolck}
rst2html README.txt --stylesheet=style.css index.html
[[ -z $1 ]] && exit 0;
ssh "$sfuser",mlabwrap@shell.sourceforge.net create && \
scp index.html *.css *.png "$sfuser"@shell.sf.net:/home/groups/m/ml/mlabwrap/htdocs/

