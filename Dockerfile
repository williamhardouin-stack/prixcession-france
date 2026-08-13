FROM apify/actor-python:3.14

COPY requirements.txt ./

RUN python --version \
    && pip install --no-cache-dir -r requirements.txt

COPY . ./

RUN python -m compileall -q .

CMD ["python", "main.py"]
