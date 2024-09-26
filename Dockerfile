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

# Install Celery and Redis (used for asynchronous tasks)
RUN pip install celery[redis]

# Copy the Django project files into the container
COPY . /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Expose the Django dev server port
EXPOSE 8001

# Run Django development server and Celery worker
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8001 & celery -A shopify_django_app worker --loglevel=info"]
