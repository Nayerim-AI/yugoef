# Use an official Python runtime as a parent image
FROM python:3.11-slim

WORKDIR /app

# Copy project files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY yugoef/ yugoef/
COPY .env.example .env

# Expose the API port
EXPOSE 8000

# Run the FastAPI server
CMD ["uvicorn", "yugoef.main:app", "--host", "0.0.0.0", "--port", "8000"]
