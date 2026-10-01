FROM python:3.12-alpine
WORKDIR /app
COPY app.py /app/app.py
COPY static /app/static
EXPOSE 3002
CMD ["python3", "-u", "/app/app.py"]
