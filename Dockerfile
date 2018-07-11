FROM python:3.6

run mkdir opt/API
add ./requirements.txt opt/API
RUN pip install -r opt/API/requirements.txt
add ./eemCli /opt/eemCli
add ./expether_API opt/API

CMD ["python", "opt/API/app.py"]
