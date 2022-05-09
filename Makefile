# -*- Makefile -*-

-include $(buildTop)/share/dws/prefix.mk

srcDir        ?= .
installTop    ?= $(VIRTUAL_ENV)
binDir        ?= $(installTop)/bin
CONFIG_DIR    ?= $(srcDir)
# XXX CONFIG_DIR should really be $(installTop)/etc/testsite
LOCALSTATEDIR ?= $(installTop)/var

installDirs   ?= install -d
installFiles  ?= install -p -m 644
NPM           ?= npm
PYTHON        := $(binDir)/python
SQLITE        ?= sqlite3

RUN_DIR       ?= $(srcDir)
DB_NAME       ?= $(RUN_DIR)/db.sqlite

MANAGE        := TESTSITE_SETTINGS_LOCATION=$(CONFIG_DIR) RUN_DIR=$(RUN_DIR) $(PYTHON) manage.py

# Django 1.7,1.8 sync tables without migrations by default while Django 1.9
# requires a --run-syncdb argument.
# Implementation Note: We have to wait for the config files to be installed
# before running the manage.py command (else missing SECRECT_KEY).
RUNSYNCDB     = $(if $(findstring --run-syncdb,$(shell cd $(srcDir) && $(MANAGE) migrate --help 2>/dev/null)),--run-syncdb,)

install:: install-conf
	cd $(srcDir) && $(PYTHON) ./setup.py --quiet \
		build -b $(CURDIR)/build install


install-conf:: $(DESTDIR)$(CONFIG_DIR)/credentials \
                $(DESTDIR)$(CONFIG_DIR)/gunicorn.conf
	install -d $(DESTDIR)$(LOCALSTATEDIR)/db
	install -d $(DESTDIR)$(LOCALSTATEDIR)/run
	install -d $(DESTDIR)$(LOCALSTATEDIR)/log/gunicorn


$(DESTDIR)$(CONFIG_DIR)/credentials: $(srcDir)/testsite/etc/credentials
	install -d $(dir $@)
	@if [ ! -f $@ ] ; then \
		sed \
		-e "s,\%(SECRET_KEY)s,`$(PYTHON) -c 'import sys ; from random import choice ; sys.stdout.write("".join([choice("abcdefghijklmnopqrstuvwxyz0123456789!@#$%^*-_=+") for i in range(50)]))'`," \
		-e "s,STRIPE_PUB_KEY = \"\",STRIPE_PUB_KEY = \"$(STRIPE_PUB_KEY)\"," \
		-e "s,STRIPE_PRIV_KEY = \"\",STRIPE_PRIV_KEY = \"$(STRIPE_PRIV_KEY)\","\
		-e "s,STRIPE_CLIENT_ID = \"\",STRIPE_CLIENT_ID = \"$(STRIPE_CLIENT_ID)\","\
			$< > $@ ; \
	else \
		echo "warning: We are keeping $@ intact but $< contains updates that might affect behavior of the testsite." ; \
	fi


$(DESTDIR)$(CONFIG_DIR)/gunicorn.conf: $(srcDir)/testsite/etc/gunicorn.conf
	install -d $(dir $@)
	[ -f $@ ] || sed \
		-e 's,%(LOCALSTATEDIR)s,$(LOCALSTATEDIR),' $< > $@


initdb-with-dummydata: initdb
	cd $(srcDir) && $(MANAGE) load_test_transactions


initdb:
	-rm -f $(DB_NAME)
	cd $(srcDir) && $(MANAGE) migrate $(RUNSYNCDB) --noinput
	echo "CREATE UNIQUE INDEX uniq_email ON auth_user(email);" | $(SQLITE) $(DB_NAME)
	cd $(srcDir) && $(MANAGE) loaddata \
        testsite/fixtures/initial_data.json \
        testsite/fixtures/test_data.json \
        testsite/fixtures/50-visit-card2.json \
        testsite/fixtures/100-balance-due.json \
        testsite/fixtures/110-balance-checkout.json \
        testsite/fixtures/120-subscriptions.json


doc:
	$(installDirs) build/docs
	cd $(srcDir) && sphinx-build -b html ./docs $(PWD)/build/docs


vendor-assets-prerequisites: $(installTop)/.npm/djaodjin-saas-packages

$(installTop)/.npm/djaodjin-saas-packages: $(srcDir)/testsite/package.json
	$(installFiles) $^ $(installTop)
	$(NPM) install --loglevel verbose --cache $(installTop)/.npm --tmp $(installTop)/tmp --prefix $(installTop)
	$(installDirs) -d $(srcDir)/testsite/static/vendor
	$(installFiles) $(installTop)/node_modules/jquery/dist/jquery.js $(srcDir)/testsite/static/vendor
	$(installFiles) $(installTop)/node_modules/moment/moment.js $(srcDir)/testsite/static/vendor
	$(installFiles) $(installTop)/node_modules/moment-timezone/builds/moment-timezone-with-data.js $(srcDir)/testsite/static/vendor
	$(installFiles) $(installTop)/node_modules/vue/dist/vue.js $(srcDir)/testsite/static/vendor
	$(installFiles) $(installTop)/node_modules/vue-croppa/dist/vue-croppa.js $(srcDir)/testsite/static/vendor
	$(installFiles) $(installTop)/node_modules/vue-infinite-loading/dist/vue-infinite-loading.js $(srcDir)/testsite/static/vendor
	touch $@
