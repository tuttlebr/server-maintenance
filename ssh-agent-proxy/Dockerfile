FROM alpine:3.21

RUN apk add --no-cache socat

COPY --chmod=0755 entrypoint.sh /usr/local/bin/ssh-agent-proxy

ENTRYPOINT ["/usr/local/bin/ssh-agent-proxy"]
