FROM python:3.11-slim-bullseye

WORKDIR /app

COPY requirements.txt .

# Install CPU-only torch (smaller/faster than default CUDA wheels)
RUN pip install --no-cache-dir --default-timeout=2000 --retries 10 torch --index-url https://download.pytorch.org/whl/cpu

# Install other requirements
RUN pip install --no-cache-dir --default-timeout=2000 --retries 10 -r requirements.txt

COPY . .

EXPOSE 8004

CMD ["python", "main.py"]
