#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# Copyright (c) 2017, Adfinis SyGroup AG
# All rights reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""
import logging
from OpenSSL import crypto
from acme_powerdns import acme_client


logging.basicConfig(level=logging.INFO)

ac = acme_client.Account(
    logging,
    'https://acme-staging.api.letsencrypt.org/directory'
)

# create an ACME account
regr, acme, account_key = ac.create_account(
    'account.key',
)

# create certificate request
cr = acme_client.CertRequest(
    ac,
    acme,
    regr,
    account_key,
)
tokens = cr.request_tokens(
    [
        'www.example.com',
        'mail.example.com',
    ],
    'dns01',
)

for token in tokens:
    # TODO: create all tokens
    # save the token['validation'] for each token['domain']

with open(settings.CSR, 'rb') as fp:
    csr = crypto.load_certificate_request(
        crypto.FILETYPE_PEM,
        fp.read()
    )
cert, chain = cr.answer_challenges(
    csr,
)
with open(settings.CRT, 'wb') as f:
    for crt in cert:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, crt))
with open(settings.CHAIN, 'wb') as f:
    for crt in chain:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, crt))

for token in tokens:
    # TODO: create all tokens
    # delete the token['validation'] for each token['domain']
"""

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from acme import client
from acme import challenges
from acme import messages
from acme import jose


class Account:

    def __init__(self, logging, directory_url):
        """Initialize a new ACME client.

        Args:
            logging: a logging object.
            directory_url: the ACME directory url (e.g. staging directory).
        """
        self._logging = logging
        self._acme = None
        self._directory_url = directory_url

    def create_account(self, keyfile) -> (
            messages.RegistrationResource, jose.JWKRSA):
        """Create a new account on the directory server.
        If the account exists, nothing will happen.

        Args:
            keyfile: file with the private RSA account key.
        """
        with open(keyfile, 'rb') as kf:
            try:
                key_contents = kf.read()
                account_key = jose.JWKRSA(
                    key=serialization.load_pem_private_key(
                        key_contents,
                        None,
                        default_backend()
                    )
                )
            except BaseException as e:
                raise Exception("Key {} couldn't be loaded".format(e))

        try:
            self._acme = client.Client(
                self._directory_url,
                account_key,
            )

            self._regr = self._acme.register()
            self._logging.info(
                'Auto-accepting TOS: %s',
                self._regr.terms_of_service,
            )
            self._acme.agree_to_tos(self._regr)
            self._logging.debug(self._regr)
        except BaseException as e:
            raise SystemError("Account not created: {}".format(e))
        return (self._regr, self._acme, account_key)


class CertRequest:

    def __init__(self, client, acme, regr, account_key):
        self._client = client
        self._acme = acme
        self._regr = regr
        self._challenges = list()
        self._account_key = account_key

    def request_tokens(self, domains, ctype) -> list:
        """Request tokens for a list of domains.

        Args:
            domains: a list of domains (as strings).

        Return: a list of dicts with domain and token.
        """
        tokens = list()
        try:
            challenge_class = {
                'dns01': challenges.DNS01,
                'http01': challenges.HTTP01,
                'tlssni01': challenges.TLSSNI01,
            }[ctype]
        except KeyError:
            raise ValueError('Type {} is not defined'.format(ctype))
        for domain in domains:
            # request a challenge
            try:
                authzr = self._acme.request_domain_challenges(
                    domain,
                    new_authzr_uri=self._regr.new_authzr_uri,
                )

                authzr, authzr_response = self._acme.poll(authzr)
            except BaseException as e:
                raise SystemError("Challenge requesting failed: {}".format(e))

            challb = None
            for c in authzr.body.combinations:
                if len(c) == 1 and isinstance(
                        authzr.body.challenges[c[0]].chall,
                        challenge_class):
                    challb = authzr.body.challenges[c[0]]
            if challb is None:
                raise LookupError('{} not in {}'.format(ctype, authzr))

            response, validation = challb.response_and_validation(
                self._account_key
            )

            self._challenges.append({
                'authzr': authzr,
                'challb': challb,
                'response': response,
                'validation': validation,
            })
            tokens.append({
                'domain': domain,
                'validation': validation,
            })

        return tokens

    def answer_challenges(self, csr):
        """Answer all challenges.

        Args:
            csr_file: the filename of the csr file.
            crt_file: the filename of the cert file.
            chain_file: the filename of the chain file.
        """
        authzrs = list()
        for authzr in self._challenges:
            try:
                self._acme.answer_challenge(
                    authzr['challb'],
                    authzr['response'],
                )
            except BaseException as e:
                raise SystemError("Challenge answering failed: {}".format(e))
            authzrs.append(authzr['authzr'])

        try:
            crt, updated_authzrs = self._acme.poll_and_request_issuance(
                jose.util.ComparableX509(csr),
                authzrs,
            )
        except BaseException as e:
            raise SystemError("Requesting certificate failed: {}".format(e))

        try:
            cert = [crt.body]
            chain = self._acme.fetch_chain(crt)
        except BaseException as e:
            raise ValueError(
                "Extracting certificate and getting chain failed: {}".format(e)
            )
        return (cert, chain)


def _monkeypatch_post(self, url, obj,
                      content_type=client.ClientNetwork.JSON_CONTENT_TYPE,
                      check_response=True, **kwargs):
    data = self._wrap_in_jws(obj, self._get_nonce(url))
    response = self._send_request('POST', url, data=data, **kwargs)
    self._add_nonce(response)
    if check_response:
        return self._check_response(response, content_type=content_type)
    else:
        return response


def _monkeypatch_register(self, new_reg=None):
    new_reg = new_reg or messages.NewRegistration()
    response = self.net.post(
        self.directory[new_reg],
        new_reg,
        check_response=False,
    )
    loc = None
    if response.status_code == client.http_client.CONFLICT and \
            response.headers.get('Location'):
        reg = messages.UpdateRegistration()
        loc = response.headers.get('Location')
        response = self.net.post(loc, reg)
    return self._regr_from_response(response, uri=loc)


client.ClientNetwork.post = _monkeypatch_post
client.Client.register = _monkeypatch_register
