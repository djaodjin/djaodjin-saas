# -*- Makefile -*-

-include $(buildTop)/share/dws/prefix.mk

srcDir        ?= .
installTop    ?= $(VIRTUAL_ENV)
binDir        ?= $(installTop)/bin

PYTHON        := $(binDir)/python
installDirs   ?= install -d

install::
	cd $(srcDir) && $(PYTHON) ./setup.py --quiet \
		build -b $(CURDIR)/build install

initdb:
	-rm -f saas_testsite.sqlite
	cd $(srcDir) && $(PYTHON) ./manage.py syncdb --noinput
	cd $(srcDir) && $(PYTHON) ./manage.py loaddata \
						saas/fixtures/saas_data.json
	cd $(srcDir) && $(PYTHON) ./manage.py loaddata \
						testsite/fixtures/test_data.json

doc:
	$(installDirs) docs
	cd $(srcDir) && sphinx-build -b html ./docs $(PWD)/docs
