# syntax=docker/dockerfile:1

# Comments are provided throughout this file to help you get started.
# If you need more help, visit the Dockerfile reference guide at
# https://docs.docker.com/engine/reference/builder/

ARG PYTHON_VERSION=3.11.6
FROM python:${PYTHON_VERSION}-slim as base

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create a non-privileged user that the app will run under.
# See https://docs.docker.com/go/dockerfile-user-best-practices/
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

RUN apt-get update && apt-get install -y \
	libturbojpeg0 \
	libgl1 \
	libgphoto2-dev \
	fonts-noto-color-emoji \
	libglib2.0-0 \
	libsm6 \
	libxrender1 \
	libxext6

# Download dependencies as a separate step to take advantage of Docker's caching.
# Leverage a cache mount to /root/.cache/pip to speed up subsequent builds.
# Leverage a bind mount to requirements.txt to avoid having to copy them into
# into this layer.
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install photobooth-app

WORKDIR /photobooth-data
RUN chown -R appuser:appuser /photobooth-data
#RUN chmod 777 /photobooth-data

# Switch to the non-privileged user to run the application.
USER appuser

# Copy the source code into the container.
#COPY . .

# Expose the port that the application listens on.
EXPOSE 80

# Run the application.
CMD python -m photobooth

