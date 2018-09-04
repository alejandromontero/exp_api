FROM python:3.6

run mkdir opt/API
add ./requirements.txt opt/API
RUN pip install -r opt/API/requirements.txt
add ./eemCli /opt/eemCli
add ./expether_API /opt/API

ARG EEM_IP=10.0.26.50
ARG EEM_PORT=30500

run cp /opt/API/config/EEM/eemcli.conf_template /opt/API/config/EEM/eemcli.conf
run sed	-i s/##EEM_IP##/$EEM_IP/g /opt/API/config/EEM/eemcli.conf && \
	sed -i s/##EEM_PORT##/$EEM_PORT/g /opt/API/config/EEM/eemcli.conf

CMD ["python", "opt/API/app.py"]
