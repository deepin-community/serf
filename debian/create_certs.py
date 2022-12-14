#!/usr/bin/env python

#
# ===================================================================
#   Licensed to the Apache Software Foundation (ASF) under one
#   or more contributor license agreements.  See the NOTICE file
#   distributed with this work for additional information
#   regarding copyright ownership.  The ASF licenses this file
#   to you under the Apache License, Version 2.0 (the
#   "License"); you may not use this file except in compliance
#   with the License.  You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
#   Unless required by applicable law or agreed to in writing,
#   software distributed under the License is distributed on an
#   "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#   KIND, either express or implied.  See the License for the
#   specific language governing permissions and limitations
#   under the License.
# ===================================================================
#

# This script creates the private keys and certificates required for 
# running the serf test suite.
# 
# It should be run from the test/certs folder without arguments.
# Certificates will be created in the test/certs folder, private keys in the
# test/certs/private folder.
#
# You'll need to install pyOpenSSL for this script to work.

from OpenSSL import crypto, SSL
from calendar import timegm
from datetime import datetime

# for serf, update this number every time the certs are updated.
SERIAL_NUMBER=100020

KEY_ALGO=crypto.TYPE_RSA
KEY_SIZE=2048
KEY_CIPHER='DES3'
SIGN_ALGO='SHA256'
VALID_DAYS=365 * 3

def create_key(keyfile='', passphrase=None):
    key = crypto.PKey()
    key.generate_key(KEY_ALGO, KEY_SIZE)
    if passphrase:
        open(keyfile, "wb").write(crypto.dump_privatekey(crypto.FILETYPE_PEM,
                                                         key, KEY_CIPHER, 
                                                         passphrase))
    else:
        open(keyfile, "wb").write(crypto.dump_privatekey(crypto.FILETYPE_PEM,
                                                         key))

    return key

def create_pkcs12(clientkey, clientcert, issuer, pkcs12file, passphrase=None):
    pkcs12 = crypto.PKCS12()

    pkcs12.set_certificate(clientcert)
    pkcs12.set_privatekey(clientkey)
    pkcs12.set_ca_certificates([issuer])
    open(pkcs12file, "wb").write(pkcs12.export(passphrase=passphrase,
                                               iter=2048, maciter=2048))

def create_crl(revokedcert, cakey, cacert, crlfile, next_crl_days=VALID_DAYS):
    crl = crypto.CRL()
    revoked = crypto.Revoked()

    serial_number = b"%x" % revokedcert.get_serial_number()
    now = datetime.utcnow()
    now_str = now.strftime('%Y%m%d%H%M%SZ').encode('utf-8')

    revoked.set_serial(serial_number)
    revoked.set_reason(b'unspecified')
    revoked.set_rev_date(now_str)   # revoked as of now

    crl.add_revoked(revoked)
    try:
        exported = crl.export(cacert, cakey, days=next_crl_days, digest=b"md5")
    except TypeError:
        # Some very old versions of pyopenssl (such as the one on macOS)
        # do not support the 'digest' keyword argument.
        exported = crl.export(cacert, cakey, days=next_crl_days)
    open(crlfile, "wb").write(exported)

# subjectAltName
def create_cert(subjectkey, certfile, issuer=None, issuerkey=None, country='', 
                state='', city='', org='', ou='', cn='', email='', ca=False, 
                valid_before=0, days_valid=VALID_DAYS, subjectAltName=None,
                ocsp_responder_url=None, ocsp_signer=False):
    '''
    Create a X509 signed certificate.
    
    subjectAltName
        Array of fully qualified subject alternative names (use OpenSSL syntax):
        For a DNS entry, use: [b'DNS:localhost']. Other options are b'email', b'URI', b'IP'.
    '''
    cert = crypto.X509()

    cert.set_version(3-1) # version 3, starts at 0
    cert.get_subject().C  = country
    cert.get_subject().ST = state
    cert.get_subject().L  = city 
    cert.get_subject().O  = org 
    cert.get_subject().OU = ou
    if cn:
        cert.get_subject().CN = cn
    cert.get_subject().emailAddress = email
    cert.set_serial_number(SERIAL_NUMBER)
    cert.set_pubkey(subjectkey)
    
    cert.gmtime_adj_notBefore(valid_before * 24 * 3600)
    cert.gmtime_adj_notAfter(days_valid * 24 * 3600)

    if issuer is None:
        issuer = cert # self signed
        issuerkey = subjectkey
    cert.set_issuer(issuer.get_subject())
    
    if ca:
        cert.add_extensions([
            crypto.X509Extension(b"basicConstraints", False,
                                 b"CA:TRUE"),
            crypto.X509Extension(b"subjectKeyIdentifier", False, b"hash",
                                 subject=cert)
            ])
        cert.add_extensions([
            crypto.X509Extension(b"authorityKeyIdentifier", False,
                                 b"keyid:always", issuer=issuer)
            ])

    if subjectAltName is not None:
        critical = True if not cn else False
        cert.add_extensions([
            crypto.X509Extension(b'subjectAltName', critical, ", ".join(subjectAltName).encode('utf-8'))])

    if ocsp_responder_url is not None:
        cert.add_extensions([
            crypto.X509Extension(b'authorityInfoAccess', False,
                                 'OCSP;URI:{}'.format(ocsp_responder_url).encode('utf-8'))])

    if ocsp_signer:
        cert.add_extensions([
            crypto.X509Extension(b'extendedKeyUsage', True, b'OCSPSigning')
        ])

    cert.sign(issuerkey, SIGN_ALGO)

    open(certfile, "wb").write(crypto.dump_certificate(crypto.FILETYPE_PEM,
                                                       cert))
    return cert

if __name__ == '__main__':
    # root CA key pair and certificate.
    # This key will be used to sign the intermediate CA certificate
    rootcakey = create_key('private/serfrootcakey.pem', b'serftest')

    rootcacert = create_cert(subjectkey=rootcakey, 
                             certfile='serfrootcacert.pem',
                             country='BE', state='Antwerp', city='Mechelen', 
                             org='In Serf we trust, Inc.', 
                             ou='Test Suite Root CA', cn='Serf Root CA', 
                             email='serfrootca@example.com', ca=True)

    # intermediate CA key pair and certificate
    # This key will be used to sign all server certificates
    cakey = create_key('private/serfcakey.pem', b'serftest')

    cacert = create_cert(subjectkey=cakey, certfile='serfcacert.pem',
                         issuer=rootcacert, issuerkey=rootcakey,
                         country='BE', state='Antwerp', city='Mechelen', 
                         org='In Serf we trust, Inc.', 
                         ou='Test Suite CA', cn='Serf CA', 
                         email='serfca@example.com', ca=True)

    # server key pair
    # server certificate, no errors
    serverkey = create_key('private/serfserverkey.pem', b'serftest')

    servercert = create_cert(subjectkey=serverkey, 
                             certfile='serfservercert.pem',
                             issuer=cacert, issuerkey=cakey,
                             country='BE', state='Antwerp', city='Mechelen', 
                             org='In Serf we trust, Inc.', 
                             ou='Test Suite Server', cn='localhost', 
                             email='serfserver@example.com')

    # server certificate that expired a year ago
    expiredcert = create_cert(subjectkey=serverkey, 
                              certfile='serfserver_expired_cert.pem',
                              issuer=cacert, issuerkey=cakey,
                              country='BE', state='Antwerp', city='Mechelen', 
                              org='In Serf we trust, Inc.', 
                              ou='Test Suite Server', cn='localhost', 
                              email='serfserver@example.com',
                              days_valid=-365)

    # server certificate that will be valid in 10 years
    expiredcert = create_cert(subjectkey=serverkey, 
                              certfile='serfserver_future_cert.pem',
                              issuer=cacert, issuerkey=cakey,
                              country='BE', state='Antwerp', city='Mechelen',
                              org='In Serf we trust, Inc.', 
                              ou='Test Suite Server', cn='localhost', 
                              email='serfserver@example.com',
                              valid_before=10*365,
                              days_valid=13*365)

    # server certificate with SubjectAltName and empty CN
    san_nocncert = create_cert(subjectkey=serverkey,
                               certfile='serfserver_san_nocn_cert.pem',
                               issuer=cacert, issuerkey=cakey,
                               country='BE', state='Antwerp', city='Mechelen',
                               org='In Serf we trust, Inc.',
                               ou='Test Suite Server',
                               cn=None,
                               email='serfserver@example.com',
                               days_valid=13*365,
                               subjectAltName=['DNS:localhost'])

    # server certificate with OCSP responder URL
    ocspcert = create_cert(subjectkey=serverkey,
                           certfile='serfserver_san_ocsp_cert.pem',
                           issuer=cacert, issuerkey=cakey,
                           country='BE', state='Antwerp', city='Mechelen',
                           org='In Serf we trust, Inc.',
                           ou='Test Suite Server',
                           cn='localhost',
                           email='serfserver@example.com',
                           days_valid=13*365,
                           subjectAltName=['DNS:localhost'],
                           ocsp_responder_url='http://localhost:17080')

    # OCSP responder certifi
    ocsprspcert = create_cert(subjectkey=serverkey,
                              certfile='serfocspresponder.pem',
                              issuer=cacert, issuerkey=cakey,
                              country='BE', state='Antwerp', city='Mechelen',
                              org='In Serf we trust, Inc.',
                              ou='Test Suite Server',
                              cn='localhost',
                              email='serfserver@example.com',
                              days_valid=13*365,
                              ocsp_signer=True)

    # client key pair and certificate
    clientkey = create_key('private/serfclientkey.pem', b'serftest')

    clientcert = create_cert(subjectkey=clientkey, 
                             certfile='serfclientcert.pem',
                             issuer=cacert, issuerkey=cakey,
                             country='BE', state='Antwerp', city='Mechelen', 
                             org='In Serf we trust, Inc.', 
                             ou='Test Suite Client', cn='Serf Client', 
                             email='serfclient@example.com')

    clientpkcs12 = create_pkcs12(clientkey, clientcert, cacert, 
                                 'serfclientcert.p12', b'serftest')

    # Note that this creates a v1 CRL file without extensions set, and with 
    # MD5 hash. Not ideal, but pyOpenSSL doesn't support more than this.
    # 
    # crl
    crl = create_crl(servercert, cakey, cacert, b'serfservercrl.pem')
