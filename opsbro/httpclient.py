import requests as rq

# Some old requests libs do not have rq.packages.urllib3 and direclty map them to rq.exceptions.RequestException
# like in ubuntu 14.04 version
if hasattr(rq, 'packages'):
    HTTP_EXCEPTIONS = (rq.exceptions.RequestException, rq.packages.urllib3.exceptions.HTTPError)
else:
    HTTP_EXCEPTIONS = (rq.exceptions.RequestException, )
