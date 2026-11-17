# A hivatalos Caddy-kép a Cloudflare DNS-pluginnal, a DNS-alapú tanúsítványhoz.
FROM docker.io/library/caddy:2.11.7-builder AS builder
RUN xcaddy build --with github.com/caddy-dns/cloudflare

FROM docker.io/library/caddy:2.11.7
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
