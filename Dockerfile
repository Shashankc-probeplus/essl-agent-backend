# Use the official Python image from Docker Hub
FROM python:3.11-slim

# Set up the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Copy the main.py file into the container
COPY app/. /app/app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8100 for the FastAPI application
EXPOSE 8100

# Run the FastAPI application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100", "--reload"]