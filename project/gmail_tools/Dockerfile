FROM python:3.9-slim-buster
WORKDIR /app
COPY src/ /app/src
RUN pip install --no-cache-dir -r src/requirements.txt
CMD ["python", "-m", "src.authenticate"] # Default command, but will be overridden