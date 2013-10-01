# -*- Makefile -*-

-include $(buildTop)/share/dws/prefix.mk

srcDir      ?= .

install::
	cd $(srcDir) && python ./setup.py install

initdb:
	-rm -f saas_testsite.sqlite
	cd $(srcDir) && python ./manage.py syncdb --noinput
