# Base image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    python3-dev \
    && apt-get clean

# Install dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the project files into the container
COPY . /app/

# Expose the port that Django will run on
EXPOSE 8000

# Run the Django development server (or use gunicorn for production)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "shopify_django_app.wsgi:application"]
