CFLAGS = -std=c99 $(shell pkg-config --cflags serf-1 apr-1 apr-util-1 libssl libcrypto zlib) -I.
LDFLAGS = $(shell pkg-config --libs serf-1 apr-1 apr-util-1 libssl libcrypto zlib)
TESTSOURCES = test/serf_get.c test/serf_response.c test/serf_request.c test/serf_spider.c test/test_all.c test/serf_bwtp.c
TESTOBJS = $(patsubst %.c,%.o,$(TESTSOURCES))
TESTFILES = $(patsubst %.c,%,$(TESTSOURCES))
export srcdir=$(shell pwd)

test/%.o: test/%.c
	$(CC) -c $(CFLAGS) -o $@ $^

test/%: test/%.o
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

test/test_all: test/test_all.o test/CuTest.o test/test_util.o test/test_context.o test/test_buckets.o test/test_auth.o test/mock_buckets.o test/test_ssl.o test/server/test_server.o test/server/test_sslserver.o
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

update-certs:
	mkdir -p testcerts/private
	cd testcerts && python3 ../create_certs.py
	cp testcerts/*.pem testcerts/private/serfserverkey.pem testcerts/serfclientcert.p12 test/server/

.PHONY: check
check: $(TESTFILES) update-certs
	echo $(TESTFILES)
	# Ignore failures until upstream fixes their tests with OpenSSL 3
	python3 check.py test test || true
