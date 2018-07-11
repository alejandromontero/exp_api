FROM python:3.6

run mkdir /API
add ./expether_API /API
add ./requirements.txt /API
RUN pip install -r /API/requirements.txt

CMD ["python", "/API/app.py"]
