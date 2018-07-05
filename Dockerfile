FROM python:3.6

run mkdir /API
add ./expether_API /API
RUN pip install -r /API/requirements.txt

expose 5555
CMD ["python", "/API/app.py"]
