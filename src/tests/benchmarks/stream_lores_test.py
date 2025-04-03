import io
import logging

import cv2
import numpy
import pytest
from av import open as av_open
from av.video.reformatter import Interpolation, VideoReformatter
from PIL import Image
from simplejpeg import decode_jpeg, encode_jpeg, encode_jpeg_yuv_planes
from turbojpeg import TurboJPEG

turbojpeg = TurboJPEG()
logger = logging.getLogger(__name__)


def pyav_lores_scale():
    input_device = av_open("src/tests/assets/video4k.mjpg")

    reformatter = VideoReformatter()

    with input_device:
        input_stream = input_device.streams.video[0]
        # shall speed up processing, ... lets keep an eye on this one...
        input_stream.thread_type = "AUTO"
        input_stream.thread_count = 0
        # lores stream width/height
        rW = input_stream.width // 2
        rH = input_stream.height // 2

        for frame in input_device.decode(input_stream):
            resized_frame = reformatter.reformat(frame, width=rW, height=rH, interpolation=Interpolation.BILINEAR, format="yuv420p").to_ndarray()

            _ = encode_jpeg_yuv_planes(
                Y=resized_frame[:rH],
                U=resized_frame.reshape(rH * 3, rW // 2)[rH * 2 : rH * 2 + rH // 2],
                V=resized_frame.reshape(rH * 3, rW // 2)[rH * 2 + rH // 2 :],
                quality=85,
                fastdct=True,
            )


def pyav_turbojpeg_scale():
    input_device = av_open("src/tests/assets/video4k.mjpg")

    with input_device:
        input_stream = input_device.streams.video[0]
        # shall speed up processing, ... lets keep an eye on this one...
        input_stream.thread_type = "AUTO"
        input_stream.thread_count = 0
        # lores stream width/height

        for packet in input_device.demux():  # forever
            if not packet.buffer_size:
                continue

            # Decode with downscaling by a factor of 2 (image size reduced by half)
            _ = turbojpeg.scale_with_quality(bytes(packet), quality=85, scaling_factor=(1, 2))


def pyav_simplejpeg_scale():
    input_device = av_open("src/tests/assets/video4k.mjpg")

    with input_device:
        input_stream = input_device.streams.video[0]
        # shall speed up processing, ... lets keep an eye on this one...
        input_stream.thread_type = "AUTO"
        input_stream.thread_count = 0
        # lores stream width/height

        for packet in input_device.demux():  # forever
            if not packet.buffer_size:
                continue

            # Decode with downscaling by a factor of 2 (image size reduced by half)
            decoded_img = decode_jpeg(bytes(packet), min_factor=2)
            _ = encode_jpeg(
                decoded_img,
                quality=85,
                fastdct=True,
            )


def pyav_pillow_scale():
    input_device = av_open("src/tests/assets/video4k.mjpg")

    with input_device:
        input_stream = input_device.streams.video[0]
        # shall speed up processing, ... lets keep an eye on this one...
        input_stream.thread_type = "AUTO"
        input_stream.thread_count = 0

        # lores stream width/height
        rW = input_stream.width // 2
        rH = input_stream.height // 2

        for packet in input_device.demux():  # forever
            print(packet)
            if not packet.buffer_size:
                continue

            image = Image.open(io.BytesIO(bytes(packet)))
            image.thumbnail((rW, rH), Image.Resampling.BILINEAR)  # bicubic for comparison, does not upscale, which is what we want.
            image.save(io.BytesIO(), "jpeg")


def pyav_cv2_scale():
    input_device = av_open("src/tests/assets/video4k.mjpg")

    with input_device:
        input_stream = input_device.streams.video[0]
        # shall speed up processing, ... lets keep an eye on this one...
        input_stream.thread_type = "AUTO"
        input_stream.thread_count = 0

        for packet in input_device.demux():  # forever
            if not packet.buffer_size:
                continue

            nparr = numpy.frombuffer(bytes(packet), numpy.uint8)
            img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            scale_percent = 50  # percent of original size
            width = int(img_np.shape[1] * scale_percent / 100)
            height = int(img_np.shape[0] * scale_percent / 100)
            dim = (width, height)

            # resize image
            img_np_resized = cv2.resize(img_np, dim, interpolation=cv2.INTER_LINEAR)

            # and encode to jpeg again
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
            result, encimg = cv2.imencode(".jpg", img_np_resized, encode_param)

            encimg.tobytes()


@pytest.mark.benchmark(group="scale_stream_lores")
def test_pyav_lores_scale(benchmark):
    benchmark(pyav_lores_scale)


@pytest.mark.benchmark(group="scale_stream_lores")
def test_pyav_turbojpeg_scale(benchmark):
    benchmark(pyav_turbojpeg_scale)


@pytest.mark.benchmark(group="scale_stream_lores")
def test_pyav_simplejpeg_scale(benchmark):
    benchmark(pyav_simplejpeg_scale)


@pytest.mark.benchmark(group="scale_stream_lores")
def test_pyav_pillow_scale(benchmark):
    benchmark(pyav_pillow_scale)


@pytest.mark.benchmark(group="scale_stream_lores")
def test_pyav_cv2_scale(benchmark):
    benchmark(pyav_cv2_scale)
