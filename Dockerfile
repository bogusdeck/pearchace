FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the Docker container
WORKDIR /app

# Install required system packages
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    python3-dev \
    && apt-get clean

# Copy the requirements file and install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the application code into the Docker container
COPY . /app/

# Expose the default port for Django/Gunicorn
EXPOSE 8000

# Command to run Gunicorn, pointing to your Django project’s WSGI application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "shopify_django_app.wsgi:application"]
