from __future__ import annotations

import logging
import shutil
import uuid
from fractions import Fraction
from pathlib import Path

import av
import av.codec.context

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

        with av.open(input_path) as input, av.open(output_path, mode="w", options={"movflags": "faststart"}) as output:
            in_stream = input.streams.video[0]
            out_stream = output.add_stream_from_template(template=in_stream)

            # compute duration in ticks; it is assumed that pts and dts have same duration, TODO: verify.
            dts_values = [p.dts for p in input.demux(in_stream) if p.dts is not None]
            duration_ts = max(dts_values) - min(dts_values)

            in_fps = in_stream.base_rate or in_stream.average_rate
            assert in_fps is not None, "could not determine the input video fps."
            assert in_stream.time_base is not None, "could not determine the input video time_base."
            frame_duration_s = 1 / in_fps
            frame_duration_ts = int(frame_duration_s / in_stream.time_base)

            # --- PASS 2: loop packets ---
            input.seek(0)
            for loop_index in range(self.loops):
                ts_offset = loop_index * (duration_ts + frame_duration_ts)

                for packet in input.demux(in_stream):
                    if packet.size == 0:  # https://pyav.basswood.io/docs/stable/cookbook/basics.html
                        continue
                    if packet.dts is None or packet.pts is None:
                        continue

                    packet.stream = out_stream
                    packet.pts = packet.pts + ts_offset
                    packet.dts = packet.dts + ts_offset

                    output.mux(packet)

                input.seek(0)

        context.video_processed = output_path
        next_step(context)


class BoomerangStep(PipelineStep):
    def __init__(self, boomerang_speed: float, drop_first_last: bool = True) -> None:
        self.boomerang_speed: float = boomerang_speed
        self.drop_first_last: bool = drop_first_last

    def __call__(self, context: VideoContext, next_step: NextStep) -> None:
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

        def encode_frame(f: av.VideoFrame, pts, offset_ts: int) -> None:
            fc = clone_frame(f)
            fc.pts = pts + offset_ts
            fc.dts = pts + offset_ts  # dts is derived from pts by pyav/ffmpeg usually, but we keep it safe...

            for packet in out_stream.encode(fc):
                output.mux(packet)

        input_path = Path(context.video_in)
        output_path = Path("tmp", f"boomerang_{uuid.uuid4().hex}").with_suffix(".mp4")

        # setup in/out containers
        with av.open(input_path) as input, av.open(output_path, mode="w", options={"movflags": "faststart"}) as output:
            # setup in/out streams
            in_stream = input.streams.video[0]
            in_stream.codec_context.thread_type = av.codec.context.ThreadType.AUTO
            in_stream.codec_context.thread_count = 0

            in_time_base = in_stream.time_base
            in_stream_duration = in_stream.duration
            in_fps = in_stream.codec_context.framerate
            assert in_time_base, "cannot determine timebase of input stream"
            assert in_stream_duration, "cannot determine duration of input stream"
            frame_duration_ts = int((1 / in_fps) / in_time_base)
            in_time_base_fraction = Fraction(in_time_base.numerator, in_time_base.denominator)
            out_scaled_time_base = in_time_base_fraction / Fraction(self.boomerang_speed).limit_denominator(100)

            out_stream = output.add_stream("h264", rate=in_fps)
            out_stream.width = in_stream.width
            out_stream.height = in_stream.height
            out_stream.time_base = out_scaled_time_base
            out_stream.pix_fmt = "yuv420p"
            out_stream.codec_context.options["tune"] = "zerolatency"  # Optional: faster encoding for real-time
            out_stream.codec_context.options["preset"] = "veryfast"
            out_stream.codec_context.thread_type = av.codec.context.ThreadType.AUTO
            out_stream.codec_context.thread_count = 0
            out_stream.codec_context.time_base = out_scaled_time_base  # Critical to sync timebase for stream/codec!
            out_stream.bit_rate = in_stream.bit_rate

            # --- PASS 1: decode all frames into RAM ---
            # This is a bit memory intensive, but for small videos it should be fine.
            # decoded frames are correctly sorted by pts/dts, no need to sort manually.
            frames: list[av.VideoFrame] = [frame.reformat(format="yuv420p") for frame in input.decode(in_stream)]
            frames_pts = [frame.pts for frame in frames]

            if len(frames) < 3:
                raise RuntimeError("Video too short for boomerang")

            # --- PASS 2: encode forward + reversed ---
            # forward: full video
            for i, f in enumerate(frames):
                encode_frame(f, frames_pts[i], 0)

            # reverse: trimmed (no first, no last) #TODO: maybe not an option in the future...
            if self.drop_first_last:
                middle_frames: list[av.VideoFrame] = frames[1:-1]
                middle_pts = frames_pts[1:-1]
                # subtract 1 frame duration to account for the removed frame if drop_first_last is True
                offset_ts = in_stream_duration - frame_duration_ts
            else:
                middle_frames = frames
                middle_pts = frames_pts
                offset_ts = in_stream_duration

            for i, f in enumerate(reversed(middle_frames)):
                encode_frame(f, middle_pts[i], offset_ts)

            # flush encoder
            for packet in out_stream.encode(None):
                output.mux(packet)

        context.video_processed = output_path
        next_step(context)
