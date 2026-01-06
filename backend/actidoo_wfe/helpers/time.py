# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

import datetime

import pytz


def dt_now_aware():
    """Returns the current datetime in UTC"""
    return datetime.datetime.now(datetime.timezone.utc)


def dt_ago_aware(**kw):
    """Substracts the given timedelta from now and returns the resulting datetime in UTC"""
    return dt_now_aware() - datetime.timedelta(**kw)


def dt_in_aware(**kw):
    """Adds the given timedelta to now and returns the resulting datetime in UTC"""
    return dt_now_aware() + datetime.timedelta(**kw)



def dt_now_naive():
    """Returns the current datetime in UTC as a timezone-naive object"""
    return dt_now_aware().replace(tzinfo=None)

def dt_ago_naive(**kw):
    """Subtracts the given timedelta from now and returns the resulting datetime as a timezone-naive object in UTC"""
    return dt_now_naive() - datetime.timedelta(**kw)

def dt_in_naive(**kw):
    """Adds the given timedelta to now and returns the resulting datetime as a timezone-naive object in UTC"""
    return dt_now_naive() + datetime.timedelta(**kw)

def to_timezone_naive_in_utc(timezone_aware_datetime):
    return timezone_aware_datetime.astimezone(datetime.timezone.utc).replace(tzinfo=None)
