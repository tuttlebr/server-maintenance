FROM alpine:3.21

RUN apk add --no-cache socat openssh-client

COPY --chmod=0755 entrypoint.sh /usr/local/bin/ssh-agent-proxy
COPY --chmod=0755 healthcheck.sh /usr/local/bin/check-ssh-agent

ENTRYPOINT ["/usr/local/bin/ssh-agent-proxy"]
