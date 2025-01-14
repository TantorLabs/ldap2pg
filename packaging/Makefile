TOPSRC_DIR=$(wildcard ..)
YUM_LABS?=$(wildcard $(TOPSRC_DIR)/../yum-labs)

default:

sdist:
	pip download --no-deps --no-binary :all: --dest $(TOPSRC_DIR)/dist ldap2pg==$(shell cd ..; python setup.py --version)

distclean:
	rm -rf ../dist/

rpm:
	$(MAKE) -C $(YUM_LABS) clean
	$(MAKE) rpm-rhel8 rpm-rhel7 rpm-rhel6

rpm-rhel%:
	docker-compose run --rm rhel$*
	cp -fl $$(readlink -e $(TOPSRC_DIR)/dist/ldap2pg-last.rpm) $(YUM_LABS)/rpms/RHEL$*-x86_64/

clean:
	docker-compose down -v

push:
	@make -C $(YUM_LABS) push createrepos clean

specs: ldap2pg-el8.spec ldap2pg-el7.spec ldap2pg-el6.spec

ldap2pg-el8.spec: Makefile ../setup.py
	cd ..; python setup.py bdist_rpm \
	  --release "1%{dist}" \
	  --build-requires "python3 python3-setuptools" \
	  --requires "python3-psycopg2 python3-ldap python3-yaml" \
	  --python "/usr/bin/python3" \
	  --spec-only
	cp -f ../dist/ldap2pg.spec $@

ldap2pg-el7.spec: Makefile ../setup.py
	cd ..; python setup.py bdist_rpm \
	  --release "1%{dist}" \
	  --build-requires "python36 python36-setuptools" \
	  --requires "python36-psycopg2 python36-ldap python36-PyYAML" \
	  --python "/usr/bin/python3.6" \
	  --spec-only
	cp -f ../dist/ldap2pg.spec $@

ldap2pg-el6.spec: Makefile ../setup.py
	cd ..; python setup.py bdist_rpm \
	  --release "1%{dist}" \
	  --build-requires "python2 python2-setuptools" \
	  --requires "python-psycopg2 python-ldap PyYAML python-logutils python-argparse" \
	  --python "/usr/bin/python2" \
	  --spec-only
	cp -f ../dist/ldap2pg.spec $@
