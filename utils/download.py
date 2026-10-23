import requests
import cbor
import time

from utils.response import Response

MAX_BYTES = 10_000_000 # hopefully no page is this big...
TIMEOUT = 10 # in seconds
TOO_LARGE_STATUS = 613


def _too_large(url, logger, actual_size = None):
    if logger is not None:
        log_str = f"Skipping {url}: response exceeds {MAX_BYTES} bytes"
        if actual_size is not None:
            log_str += f". Is {actual_size} bytes"
        logger.info(log_str)
    return Response({
        "error": f"Response exceeds {MAX_BYTES} bytes.",
        "status": TOO_LARGE_STATUS,
        "url": url
    })

def download(url, config, logger=None):
    host, port = config.cache_server

    try:
        with requests.get(
            f"http://{host}:{port}/",
            params=[("q", f"{url}"), ("u", f"{config.user_agent}")],
            stream=True, 
            timeout=TIMEOUT
        ) as resp:
            # Hope header tells us length
            length = resp.headers.get("Content-Length")
            if length is not None and int(length) > MAX_BYTES:
                return _too_large(url, logger, int(length))

            # read n+1 bytes so we know it exceeds limit
            data = resp.raw.read(MAX_BYTES + 1, decode_content=True) # Raw bytes
            if data and len(data) > MAX_BYTES:
                return _too_large(url, logger) #unknown how big it actually is

            if resp and data:
                return Response(cbor.loads(data))

            status = resp.status_code
    except requests.RequestException as e: # any exception like timeout or connection exceptions
        status = 600
        resp = e
    except (EOFError, ValueError):
        pass

    if logger is not None:
        logger.error(f"Spacetime Response error {resp} with url {url}.")
    return Response({
        "error": f"Spacetime Response error {resp} with url {url}.",
        "status": status,
        "url": url})
