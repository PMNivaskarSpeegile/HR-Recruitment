"""
Datetime normalization for the API boundary.

The project runs with ``USE_TZ = False`` and stores naive datetimes in the
server's local wall-clock (``timezone.now()`` returns ``datetime.now()``). The
React client, however, sends instants as UTC (``Date.toISOString()`` → "…Z"),
which DRF parses into a naive *UTC* datetime. Comparing that against the local
``timezone.now()`` — or storing it for later display — is off by the server's
UTC offset, so a genuinely-future time can look like it is in the past.

``to_local_naive`` reconciles an incoming value to the app's convention: naive,
in the server's local timezone. Aware values are converted; a naive value is
assumed to be UTC (how the client's data arrives) and shifted to local.
"""
import datetime as _dt

from django.utils import timezone


def to_local_naive(value):
    """Return ``value`` as a naive datetime in the server's local timezone.

    ``None`` passes through. Aware values are converted to local time; a naive
    value is treated as UTC (the client always sends UTC) before conversion."""
    if value is None:
        return value
    if timezone.is_naive(value):
        value = value.replace(tzinfo=_dt.timezone.utc)
    return value.astimezone().replace(tzinfo=None)
