# Use an official Python runtime as a parent image
FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN adduser kah --uid 568

# Set the working directory in the container to /app
WORKDIR /app

# Copy requirements.txt to the container
COPY --chown=kah:kah ./requirements.txt /app/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir pyuwsgi

# Copy the current directory contents into the container at /app
COPY --chown=kah:kah . /app

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Run the command to start uWSGI
CMD ["uwsgi", "--ini", "app.ini"]
