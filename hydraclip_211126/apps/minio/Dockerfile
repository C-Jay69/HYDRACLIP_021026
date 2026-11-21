FROM alpine:3.20
RUN apk add --no-cache curl ca-certificates
RUN curl -o /usr/local/bin/minio https://dl.min.io/server/minio/release/linux-amd64/archive/minio.RELEASE.2024-11-07T00-52-20Z \
    && chmod +x /usr/local/bin/minio
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
