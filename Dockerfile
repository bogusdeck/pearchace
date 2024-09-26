# Base image
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the application code into the Docker container
COPY . /app/

# Command to run Gunicorn or the Django dev server
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "shopify_django_app.wsgi:application"]
