from __future__ import annotations

import logging
import os
import shutil
import subprocess
import uuid
from fractions import Fraction
from pathlib import Path

import av
import cv2

from .... import LOG_PATH
from ..context import VideoContext
from ..pipeline import NextStep, PipelineStep

logger = logging.getLogger(__name__)


class LoopStep(PipelineStep):
    def __init__(self, loops: int) -> None:
        self.loops: int = loops

    def __call__(self, context: VideoContext, next_step: NextStep) -> None:
        input_path = Path(context.video_in)
        output_path = Path("tmp", f"loop_{uuid.uuid4().hex}").with_suffix(".mp4")

        if self.loops < 1:
            raise ValueError("loops must be at least 1")
        elif self.loops == 1:
            shutil.copy(input_path, output_path)

            context.video_processed = output_path
            next_step(context)

            return  # exit early.

        in_container = av.open(input_path)
        out_container = av.open(output_path, mode="w")

        in_stream = in_container.streams.video[0]
        out_stream = out_container.add_stream_from_template(template=in_stream)

        # compute duration in ticks; it is assumed that pts and dts have same duration, TODO: verify.
        dts_values = [p.dts for p in in_container.demux(in_stream) if p.dts is not None]
        duration_ts = max(dts_values) - min(dts_values)

        in_fps = in_stream.base_rate or in_stream.average_rate
        assert in_fps is not None, "could not determine the input video fps."
        assert in_stream.time_base is not None, "could not determine the input video time_base."
        frame_duration_s = 1 / in_fps
        frame_duration_ts = int(frame_duration_s / in_stream.time_base)

        # --- PASS 2: loop packets ---
        in_container.seek(0)
        for loop_index in range(self.loops):
            ts_offset = loop_index * (duration_ts + frame_duration_ts)

            for packet in in_container.demux(in_stream):
                # for packet in packets:
                if packet.dts is None:
                    continue
                if packet.pts is None:
                    continue

                packet.stream = out_stream
                packet.pts = packet.pts + ts_offset
                packet.dts = packet.dts + ts_offset

                out_container.mux(packet)

            in_container.seek(0)

        out_container.close()
        in_container.close()

        context.video_processed = output_path
        next_step(context)


class BoomerangStep(PipelineStep):
    def __init__(self, boomerang_speed: float) -> None:
        self.boomerang_speed: float = boomerang_speed

    def __call__(self, context: VideoContext, next_step: NextStep) -> None:
        input_path = Path(context.video_in)
        output_path = Path("tmp", f"boomerang_{uuid.uuid4().hex}").with_suffix(".mp4")

        # --- PASS 1: decode all frames into RAM ---
        in_container = av.open(str(input_path))
        in_stream = in_container.streams.video[0]

        frames: list[av.VideoFrame] = [frame.reformat(format="yuv420p") for frame in in_container.decode(in_stream)]
        in_container.close()

        if len(frames) < 3:
            raise RuntimeError("Video too short for boomerang")

        middle_frames: list[av.VideoFrame] = frames[1:-1]

        # --- PASS 2: encode forward + reversed ---
        out_container = av.open(str(output_path), mode="w")

        # base fps from input, scaled by boomerang speed
        in_fps = in_stream.base_rate or in_stream.average_rate
        assert in_fps is not None, "could not determine the input video fps."
        out_fps = in_fps * Fraction(self.boomerang_speed).limit_denominator(10000)

        out_stream = out_container.add_stream("h264", rate=out_fps)
        out_stream.pix_fmt = "yuv420p"
        out_stream.options = {"movflags": "+faststart"}
        out_stream.time_base = 1 / out_fps

        pts = 0

        def clone_frame(f: av.VideoFrame) -> av.VideoFrame:
            """clone the frame so forward and backward encoding use fresh frames. this is needed because during
            encoding the pts/dts and some metadata might be changed internally and the second encoding pass fails.
            all this is very efficient and consumes only microseconds usually

            Tested alternative is following, but does not work, maybe revisit in future?
            This simple clone method does not work, because the line_size is not respected.
            source line_size could be padded to match being divisible by 16, newly created frame not.

            new = av.VideoFrame(f.width, f.height, f.format.name)

            logger.warning(f"{f=}, {f.planes[0].line_size=}, {new=}, {new.planes[0].line_size=}, {f.format.name}")

            for dst, src in zip(new.planes, f.planes, strict=True):
                print(src)
                print(src.line_size)
                print(src.buffer_size)
                print(dst)
                print(dst.line_size)
                print(dst.buffer_size)

                dst.update(src)  # type: ignore # https://github.com/PyAV-Org/PyAV/pull/1286/changes
            return new

            """
            new = av.VideoFrame(f.width, f.height, f.format.name)

            for dst, src in zip(new.planes, f.planes, strict=True):
                src_mv = memoryview(src)
                dst_mv = memoryview(dst)

                src_stride = src.line_size
                dst_stride = dst.line_size

                for row in range(dst.height):
                    src_row = src_mv[row * src_stride : row * src_stride + dst_stride]
                    dst_row = dst_mv[row * dst_stride : (row + 1) * dst_stride]
                    dst_row[:] = src_row

            return new

        def encode_frame(f: av.VideoFrame) -> None:
            nonlocal pts
            fc = clone_frame(f)
            fc.pts = pts
            pts += 1  # one tick per output frame
            pkt = out_stream.encode(fc)
            if pkt:
                out_container.mux(pkt)

        # forward: full video
        for f in frames:
            encode_frame(f)

        # reverse: trimmed (no first, no last)
        for f in reversed(middle_frames):
            encode_frame(f)

        # flush encoder
        pkt = out_stream.encode(None)
        if pkt:
            out_container.mux(pkt)

        out_container.close()

        context.video_processed = output_path
        next_step(context)


class BoomerangStepFormerFfmpeg(PipelineStep):
    def __init__(self, boomerang_speed: float) -> None:
        self.boomerang_speed: float = boomerang_speed

    def __call__(self, context: VideoContext, next_step: NextStep) -> None:
        r"""
        ffmpeg -i [input path] -vf reverse -af areverse [dest path]

        # call ffmpeg command to create boomerang
        # ffmpeg -i input_loop.mp4 -filter_complex "[0]reverse[r];[0][r]concat,loop=5:250,setpts=N/55/TB" output_looped_video.mp4

        # https://www.bannerbear.com/blog/how-to-make-instagrams-boomerang-effect-with-ffmpeg/
        # ffmpeg -i input.mp4 -filter_complex "[0:v]reverse[r];[0:v][r]concat=n=2:v=1[outv]" -map "[outv]" output.mp4
        # ffmpeg -i output.mp4 -vf "setpts=1/2*PTS" output_fast.mp4

        # https://video.stackexchange.com/a/12906
        # ffmpeg -stream_loop 3 -i .\output_looped_video.mp4 -c copy output-stream.mp4

        # https://medium.com/@caglarispirli/make-boomerang-w-single-ffmpeg-command-ae6c672acb7
        # ffmpeg -i avmsakini_story.mp4 -filter_complex “[0]trim=start=3.5:end=5.5,setpts=0.5*PTS-STARTPTS,
        # split[out0][out1];[out0]reverse[r];[out1][r]concat,loop=2:250,setpts=N/25/TB[out]” -map [out] out4.mp4

        """

        # get the number of frames. This is later used to avoid duplicate frames when concatinating videos
        frame_count = int(cv2.VideoCapture(str(context.video_in)).get(cv2.CAP_PROP_FRAME_COUNT))
        speed = round(1 / self.boomerang_speed, 1)

        # generate temp filename to record to
        mp4_output_filepath = Path("tmp", f"boomerang_{uuid.uuid4().hex}").with_suffix(".mp4")

        command_general_options = [
            "-hide_banner",
            "-loglevel",
            "error",  # print only if at least error level - still all goes to the logfile.
            "-y",
        ]
        command_video_input = [
            "-i",
            str(context.video_in),
        ]
        command_video_output = [
            "-filter_complex",
            f"[0:v]trim=start_frame=1:end_frame={str(frame_count - 1)},reverse[rt];[0:v][rt]concat=n=2:v=1,setpts={speed}*PTS[outv]",
            "-map",
            "[outv]",
            "-movflags",
            "+faststart",
        ]

        ffmpeg_command = ["ffmpeg"] + command_general_options + command_video_input + command_video_output + [str(mp4_output_filepath)]
        try:
            subprocess.run(
                args=ffmpeg_command,
                check=True,
                env=dict(os.environ, FFREPORT=f"file={LOG_PATH}/ffmpeg-boomerang-last.log:level=32"),
            )
        except Exception as exc:
            logger.exception(exc)
            raise RuntimeError(f"error processing boomerang video, error: {exc}") from exc

        context.video_processed = mp4_output_filepath

        next_step(context)
