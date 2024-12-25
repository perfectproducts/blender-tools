FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY local_combined_service.py .

# Expose the FastAPI port
EXPOSE 8000

# Run the FastAPI application with Python in unbuffered mode (-u flag)
CMD ["python", "-u", "local_combined_service.py"]