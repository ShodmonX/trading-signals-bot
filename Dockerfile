FROM python:3.12-slim

ENV TZ=Asia/Tashkent

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt --no-cache-dir

COPY . .

CMD [ "python", "-m", "app.main" ]