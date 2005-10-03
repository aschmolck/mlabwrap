#!/bin/sh
rest2html README.txt --stylesheet=Steely.css index.html && scp index.html Steely.css aschmolck@shell.sf.net:/home/groups/m/ml/mlabwrap/htdocs/
