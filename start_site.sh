#!/bin/sh
/opt/poetry/bin/poetry run uvicorn --proxy-headers \
       --forwarded-allow-ips "*" \
       --host "0.0.0.0" \
       --port 8080 \
       luhack_site.site:app
