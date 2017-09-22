from opsbro.library import libstore

_HTTP_EXCEPTIONS = None


def get_http_exceptions():
    global _HTTP_EXCEPTIONS
    if _HTTP_EXCEPTIONS is not None:
        return _HTTP_EXCEPTIONS
    rq = libstore.get_requests()
    # Some old requests libs do not have rq.packages.urllib3 and direclty map them to rq.exceptions.RequestException
    # like in ubuntu 14.04 version
    if hasattr(rq, 'packages'):
        HTTP_EXCEPTIONS = (rq.exceptions.RequestException, rq.packages.urllib3.exceptions.HTTPError)
    else:
        HTTP_EXCEPTIONS = (rq.exceptions.RequestException,)
    _HTTP_EXCEPTIONS = HTTP_EXCEPTIONS
    return _HTTP_EXCEPTIONS
