FROM python:3-bullseye
RUN apt update
RUN apt -y install ffmpeg libturbojpeg0 libgl1 libgphoto2-dev fonts-noto-color-emoji
RUN apt -y install libexif12 libgphoto2-6 libgphoto2-port12 libltdl7
RUN apt -y install libvips
#RUN apt -y install pipx  pip
RUN pip install uv

WORKDIR /opt/photobooth-app
COPY . /opt/photobooth-app

RUN uv venv --system-site-packages # allow acces to system packages for libcamera/picamera2
RUN uv sync

EXPOSE 8000

ENTRYPOINT ["uv","run","photobooth"]