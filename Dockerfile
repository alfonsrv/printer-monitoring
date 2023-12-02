FROM python:3.8-slim
LABEL maintainer="Rau Systemberatung GmbH <info@rausys.de>"

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev cron \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*


RUN mkdir -p /etc/crontabs; echo -e "0 12 * * * /usr/local/bin/pytho /app/Printer-Monitoring.py --report > /proc/1/fd/1 2>/proc/1/fd/2\n" >> /etc/crontabs/root
RUN crontab /etc/crontabs/root

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY Printer-Monitoring.py /app/
RUN touch /app/Printer-Monitoring.log

CMD ["sh", "-c", "service cron start; tail -f -n 0 /app/Printer-Monitoring.log"]
