#!/bin/sh
rst2html README.txt --stylesheet=Steely.css index.html && scp index.html Steely.css surface-plot.png ugly-plot.png aschmolck@shell.sf.net:/home/groups/m/ml/mlabwrap/htdocs/
