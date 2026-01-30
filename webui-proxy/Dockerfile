ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache nginx python3

RUN mkdir -p /app/html /var/log/nginx /run/nginx

COPY app/ /app/
COPY run.sh /run.sh

RUN chmod +x /run.sh

EXPOSE 8080

CMD ["/run.sh"]
