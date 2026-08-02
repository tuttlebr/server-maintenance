#!/bin/sh
set -eu

proxy_socket=/run/fleet-agent/agent.sock
rm -f "$proxy_socket"

exec socat \
  "UNIX-LISTEN:${proxy_socket},fork,mode=0666" \
  "UNIX-CONNECT:/run/host-agent"
