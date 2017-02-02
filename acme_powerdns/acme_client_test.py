#!/usr/bin/env python
# -*- coding: UTF-8 -*-

"""Test for acme_client."""

import pytest

import logging
import acme
from acme_powerdns import acme_client


@pytest.fixture(scope='session')
def log():
    logging.basicConfig(level=logging.WARNING)
    return logging


@pytest.fixture(autouse=True, scope='session')
def account():
    ac = acme_client.Account(
        log(),
        'https://acme-staging.api.letsencrypt.org/directory',
    )
    ac.create_account('.testenv/account.key')
    return ac


def test_account_regr():
    assert type(account().get_regr()) == acme.messages.RegistrationResource


def test_account_client():
    assert type(account().get_client()) == acme.client.Client


def test_account_account_key():
    assert type(account().get_account_key()) == acme.jose.jwk.JWKRSA


def test_cert_request_request_token():
    assert type(account().get_account_key()) == acme.jose.jwk.JWKRSA
