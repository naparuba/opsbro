import requests as rq

HTTP_EXCEPTIONS = (rq.exceptions.RequestException, rq.packages.urllib3.exceptions.HTTPError)
