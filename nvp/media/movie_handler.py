"""MovieHandler handling component"""

import concurrent.futures
import glob
import io
import logging
import os
import re
import sys
from functools import wraps

import cv2
import ffmpeg
import librosa

# from moviepy.editor import *
import moviepy.editor as mpe
import numpy as np

# from mtcnn import MTCNN
from facenet_pytorch import MTCNN
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from moviepy.editor import VideoFileClip
from scipy.interpolate import interp1d

# from moviepy.audio.AudioClip import CompositeAudioClip
from nvp.core.tools import ToolsManager
from nvp.core.windowed_mean import WindowedMean
from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


# https://stackoverflow.com/questions/75231091/deepface-dont-print-logs-from-mtcnn-backend
def capture_output(func):
    """Wrapper to capture print output."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        old_stdout = sys.stdout
        new_stdout = io.StringIO()
        sys.stdout = new_stdout
        try:
            return func(*args, **kwargs)
        finally:
            sys.stdout = old_stdout

    return wrapper


class MovieHandler(NVPComponent):
    """MovieHandler component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)

        self.config = ctx.get_config()["movie_handler"]
        self.frame_index = 0
        self.face_cx = None
        self.face_cy = None
        self.target_face_cx = None
        self.target_face_cy = None
        self.face_window_len = None
        self.frame_size = None
        self.face_detector = None
        self.detect_face_func = None
        self.frame_indices = None
        self.face_pos_x = None
        self.face_pos_y = None
        self.face_sizes = None
        self.interp_fcx_func = None
        self.interp_fcy_func = None
        self.interp_fsize_func = None
        self.current_fsize = None

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        if cmd == "classify-movies":
            self.classify_movies()
            return True

        if cmd == "process-webcam-view":
            file = self.get_param("input_file")

            return self.process_webcam_view(file)

        if cmd == "find-silences":
            file = self.get_param("input_file")
            sthres = self.get_param("silence_threshold")
            mindur = self.get_param("min_silence_duration")
            minspeech = self.get_param("min_speech_duration")

            self.find_silences(file, sthres, mindur, minspeech)
            return True

        if cmd == "cut-silences":
            file = self.get_param("input_file")
            sfile = self.get_param("seg_file")

            self.cut_silences(file, sfile)
            return True

        if cmd == "preprocess-rushes":
            sthres = self.get_param("silence_threshold")
            mindur = self.get_param("min_silence_duration")
            minspeech = self.get_param("min_speech_duration")

            self.preprocess_rushes(sthres, mindur, minspeech)
            return True

        if cmd == "add-video-dates":
            cwd = self.get_cwd()

            self.add_video_dates(cwd)
            return True

        if cmd == "compose":
            file = self.get_param("input_file")
            afile = self.get_param("add_audio")
            cwd = self.get_cwd()
            if self.is_relative_path(file):
                file = self.get_path(cwd, file)
            if self.is_relative_path(afile):
                afile = self.get_path(cwd, afile)

            return self.compose_video(file, afile)

        if cmd == "concat-media":
            files = self.get_param("input_files").split(",")
            if len(files) < 2:
                logger.warning("Nothing to concatenate.")
                return True

            out_file = self.get_param("output_file", None)
            return self.concat_media(files, out_file)

        if cmd == "cut-media":
            file = self.get_param("input_file")
            duration = self.get_param("duration")
            start_time = self.get_param("start_time")
            return self.cut_media(file, duration, start_time)

        if cmd == "split-media":
            file = self.get_param("input_file")
            duration = self.get_param("duration")
            return self.split_media(file, duration)

        if cmd == "rescale-media":
            file = self.get_param("input_file")
            scale = self.get_param("scale")
            return self.rescale_media(file, scale)

        if cmd == "extract-audio":
            file = self.get_param("input_file")
            fmt = self.get_param("format")

            if "*" in file:
                files = glob.glob(file)
                logger.info("Will extract audio from %d files: %s", len(files), files)
                for file in files:
                    if not self.extract_audio(file, fmt):
                        return False
                return True
            else:
                return self.extract_audio(file, fmt)

        if cmd == "norm-sound":
            file = self.get_param("input_file")
            out_file = self.get_param("output_file", None)
            gain = self.get_param("gain")

            return self.norm_sound(file, out_file, gain)

        return False

    def detect_faces(self, frame):
        """Helper method to detect a face"""
        if self.face_detector is None:
            logger.info("Initializing MTCNN detector...")
            self.face_detector = MTCNN(
                device="cuda",
                select_largest=False,
                post_process=False,
            )
            # self.detect_face_func = capture_output(self.face_detector.detect_faces)
            # self.detect_face_func = capture_output(self.face_detector.detect)
            self.detect_face_func = self.face_detector.detect

        boxes, _ = self.detect_face_func(frame)
        # faces = self.detect_face_func(frame)

        # if faces:
        #     # Return only the first detected face
        #     return faces[0]["box"]
        if boxes is not None:
            return boxes[0]
        else:
            return None

    def process_frame(self, frame):
        """Function to process each frame of the video"""
        if self.frame_index % self.face_window_len == 0:
            logger.info("Processing frame %d", self.frame_index)

        # Perform interpolation to get the face x/y position:
        cx = self.interp_fcx_func(self.frame_index)
        cy = self.interp_fcy_func(self.frame_index)
        fsize = self.interp_fsize_func(self.frame_index)
        # logger.info("source frame size: %f", fsize)

        # Define the region of interest (ROI) around the detected face
        # hsize = (self.frame_size * 3) // 2

        self.current_fsize += (fsize - self.current_fsize) * 0.003

        hsize = self.current_fsize * 3.0 / 2.0
        hsize = min(hsize, cx, cy, frame.shape[1] - cx, frame.shape[0] - cy)

        # cx = min(max(fcx, hsize), frame.shape[1] - hsize)
        # cy = min(max(fcy, hsize), frame.shape[0] - hsize)

        roi_start_x = int(cx - hsize)
        roi_start_y = int(cy - hsize)
        roi_end_x = int(cx + hsize)
        roi_end_y = int(cy + hsize)

        # Crop and resize the video around the detected face
        cropped_frame = frame[roi_start_y:roi_end_y, roi_start_x:roi_end_x]
        resized_frame = cv2.resize(cropped_frame, (self.frame_size, self.frame_size))

        self.frame_index += 1

        return resized_frame

    def collect_face_position(self, frame, nframes):
        """Collect the face position for a given frame"""
        if self.frame_index % self.face_window_len == 0:
            logger.info("Collecting face at frame %d/%d", self.frame_index, nframes)
            face_coordinates = self.detect_faces(frame)

            if face_coordinates is not None:
                # x, y, w, h = face_coordinates
                left, top, right, bottom = face_coordinates
                # center_x, center_y = x + w // 2, y + h // 2
                center_x, center_y = (left + right) / 2.0, (top + bottom) / 2.0
                size = max(abs(right - left), abs(top - bottom))
                # logger.info("Detected frame size: %d", size)

                self.frame_indices.append(self.frame_index)
                self.face_pos_x.append(center_x)
                self.face_pos_y.append(center_y)
                self.face_sizes.append(size)

        self.frame_index += 1

        return frame

    def process_webcam_view(self, input_file):
        """Method called to process a webcam view in a given video file"""
        logger.info("Processing webcam view file %s", input_file)
        output_path = self.set_path_extension(input_file, "_centered.mp4")

        self.face_window_len = 90
        self.frame_index = 0
        self.frame_size = 512

        video_clip = VideoFileClip(input_file)

        # First we collect all the required center positions for a given frame index:
        self.frame_indices = []
        self.face_pos_x = []
        self.face_pos_y = []
        self.face_sizes = []

        logger.info("Collecting face positions...")
        nframes = int(video_clip.duration * video_clip.fps)
        # for frame in video_clip.iter_frames(fps=video_clip.fps):

        for fidx in range(0, nframes, self.face_window_len):
            self.frame_index = fidx
            frame = video_clip.get_frame(fidx / video_clip.fps)

            self.collect_face_position(frame, nframes)

        # Add a final position:
        self.frame_indices.append(nframes + 1)
        self.face_pos_x.append(self.face_pos_x[-1])
        self.face_pos_y.append(self.face_pos_y[-1])
        self.face_sizes.append(self.face_sizes[-1])

        self.current_fsize = self.face_sizes[0]

        logger.info("Done collecting %d face positions", len(self.frame_indices))

        # Process each frame of the video:
        self.frame_index = 0

        # Create an interpolation function
        # imode = "cubic"
        imode = "linear"

        self.interp_fcx_func = interp1d(np.array(self.frame_indices), np.array(self.face_pos_x), kind=imode)
        self.interp_fcy_func = interp1d(np.array(self.frame_indices), np.array(self.face_pos_y), kind=imode)
        self.interp_fsize_func = interp1d(np.array(self.frame_indices), np.array(self.face_sizes), kind=imode)

        processed_clip = video_clip.fl_image(self.process_frame)

        # Save the processed video
        processed_clip.write_videofile(output_path, audio=True)

        logger.info("Processing done.")
        return True

    def get_creation_date(self, fullpath):
        """Get the creation date from a binary file or None"""

        parser = createParser(fullpath)
        if not parser:
            logger.error("Unable to parse the file %s", fullpath)
            return None

        metadata = extractMetadata(parser)
        if metadata is None:
            logger.warning("No metadata found in %s", fullpath)
            return None

        date_str = None
        for line in metadata.exportPlaintext():
            # logger.info(line)
            if line.startswith("- Creation date: "):
                date_str = line.replace("- Creation date: ", "")
                break

        parser.close()

        return date_str

    def add_video_dates(self, input_dir):
        """Add the video date for each video file"""

        # Collect all the files recursively:
        all_files = self.get_all_files(input_dir, recursive=True)
        exts = [".mov"]

        date_pattern = r"(\d{8})_(\d{6})"

        for fname in all_files:
            ext = self.get_path_extension(fname).lower()

            fullpath = self.get_path(input_dir, fname)

            # Check if the file already contains the date:
            folder = self.get_parent_folder(fullpath)
            filename = self.get_filename(fullpath)

            dmatch = re.search(date_pattern, filename)
            if dmatch is not None:
                date_str = dmatch.group(1)
                time_str = dmatch.group(2)

                # Get the new date format:
                new_date = f"{date_str[0:4]}_{date_str[4:6]}_{date_str[6:8]}_{time_str}"

                new_fname = filename.replace(dmatch.group(0), new_date)
                logger.info("Renaming to %s", new_fname)
                dest_file = self.get_path(folder, new_fname)
                self.rename_file(fullpath, dest_file)

                continue

            if ext not in exts:
                continue

            # logger.info("Processing file %s:", fname)
            date_str = self.get_creation_date(fullpath)

            if date_str is not None:
                # date_str = date_str.replace("-", "").replace(" ", "_").replace(":", "")
                date_str = date_str.translate(str.maketrans(" -", "__", ":"))

                # If this date string is not already in the filename, we prepend it:
                filename = self.get_filename(fullpath)
                if date_str not in filename:
                    folder = self.get_parent_folder(fullpath)
                    sep = "_" if filename[0] != "_" else ""

                    new_name = self.get_path(folder, date_str + sep + filename)
                    logger.info("Renaming to: %s", new_name)
                    self.rename_file(fullpath, new_name)

    def extract_audio(self, input_file, fmt):
        """Extract the audio from a given video file"""
        tools: ToolsManager = self.get_component("tools")
        ffmpeg_path = tools.get_tool_path("ffmpeg")

        # Example command: ffmpeg -i input_video.mp4 -vn -acodec libmp3lame -q:a 2 output_audio.mp3
        cmd = [ffmpeg_path, "-threads", "8", "-i", input_file, "-vn"]

        if fmt == "wav":
            cmd += ["-acodec", "pcm_s16le", "-ar", "44100", input_file + ".wav"]
        else:
            cmd += ["-acodec", "libmp3lame", "-q:a", "2", input_file + ".mp3"]

        logger.info("Executing command: %s", cmd)
        res, rcode, outs = self.execute(cmd)

        if not res:
            logger.error("Audio extraction failed with return code %d:\n%s", rcode, outs)
            return False

        logger.info("Done writting file.")
        return True

    def norm_sound(self, input_file, out_file, gain):
        """Normalize the audio stream from a given input media file using the user provided gain"""
        if out_file is None:
            # folder = self.get_parent_folder(input_file)
            # fname = self.get_filename(input_file)
            ext = self.get_path_extension(input_file)
            out_file = self.set_path_extension(input_file, f".lnorm{ext}")

        logger.info("Should norm sound in %s and write %s", input_file, out_file)

        tools: ToolsManager = self.get_component("tools")
        ffmpeg_path = tools.get_tool_path("ffmpeg")

        # filter_str = f"[0:a]aformat=fltp:44100:stereo,volume={gain:.2f},loudnorm=I=-18:TP=-1.7:LRA=10"
        filter_str = f"[0:a]aformat=fltp:44100:stereo,volume={gain:.2f},loudnorm=I=-16:LRA=11:TP=-1.5"

        cmd = [ffmpeg_path, "-threads", "8", "-i", input_file]
        cmd += ["-filter_complex", f"{filter_str}"]
        cmd += ["-c:v", "copy", "-y", out_file]

        logger.info("Executing command: %s", cmd)
        res, rcode, outs = self.execute(cmd)

        if not res:
            logger.error("Sound normalization failed with return code %d:\n%s", rcode, outs)
            return False

        logger.info("Done writting file.")
        return True

    def cut_media(self, file, duration, start_time):
        """Concantenate a list of media files"""
        logger.info("Cutting media file %s at %s", file, duration)

        folder = self.get_parent_folder(file)
        fname = self.get_filename(file)
        out_file = self.get_path(folder, f"cut_{fname}")

        tools: ToolsManager = self.get_component("tools")
        ffmpeg_path = tools.get_tool_path("ffmpeg")

        cmd = [ffmpeg_path, "-threads", "8", "-i", file, "-ss", start_time, "-t", duration, "-c", "copy", out_file]

        # We now execute that command:
        logger.debug("Executing command: %s", cmd)
        res, rcode, outs = self.execute(cmd)

        logger.debug("Done cutting media file.")
        return True

    def rescale_media(self, file, scale_str):
        """Concantenate a list of media files"""
        logger.info("Scaling media file %s to %s", file, scale_str)

        folder = self.get_parent_folder(file)
        fname = self.get_filename(file)
        ext = self.get_path_extension(file)
        oname = self.set_path_extension(fname, f"_scaled{ext}")

        tools: ToolsManager = self.get_component("tools")
        ffmpeg_path = tools.get_tool_path("ffmpeg")

        cmd = [
            ffmpeg_path,
            "-threads",
            "8",
            "-i",
            file,
            "-vf",
            f"scale={scale_str}",
            "-c:a",
            "copy",
            oname,
        ]

        # We now execute that command:
        logger.debug("Executing command: %s", cmd)
        res, rcode, outs = self.execute(cmd)

        logger.debug("Done scaling media file.")
        return True

    def split_media(self, file, duration):
        """Concantenate a list of media files"""
        logger.info("Splitting media file %s with segments of %s", file, duration)

        folder = self.get_parent_folder(file)
        fname = self.get_filename(file)
        ext = self.get_path_extension(file)
        oname = self.set_path_extension(fname, "")
        oname += f"_%03d{ext}"

        tools: ToolsManager = self.get_component("tools")
        ffmpeg_path = tools.get_tool_path("ffmpeg")

        cmd = [
            ffmpeg_path,
            "-threads",
            "8",
            "-i",
            file,
            "-f",
            "segment",
            "-segment_time",
            duration,
            "-c",
            "copy",
            oname,
        ]

        # We now execute that command:
        logger.debug("Executing command: %s", cmd)
        res, rcode, outs = self.execute(cmd)

        logger.debug("Done cutting media file.")
        return True

    def concat_media(self, files, out_file):
        """Concantenate a list of media files"""
        self.check(len(files) >= 2, "Not enough files to perform concatenation.")

        logger.info("Concantenating video files: %s", files)

        if out_file is None:
            folder = self.get_parent_folder(files[0])
            fname = self.get_filename(files[0])
            out_file = self.get_path(folder, f"full_{fname}")

        # folder = self.get_parent_folder(files[0])

        lines = [f"file '{fname}'\n" for fname in files]
        content = "".join(lines)

        # listfile = self.get_path(folder, "concat_files.txt")
        listfile = "concat_files.txt"
        self.write_text_file(content, listfile)

        # Now we build the ffmpeg command to perform the concatenation:
        # cf. https://trac.ffmpeg.org/wiki/Concatenate
        tools: ToolsManager = self.get_component("tools")
        ffmpeg_path = tools.get_tool_path("ffmpeg")

        cmd = [ffmpeg_path, "-threads", "8", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", out_file]

        # We now execute that command:
        logger.debug("Executing command: %s", cmd)
        res, rcode, outs = self.execute(cmd)

        self.remove_file(listfile)

        if not res:
            logger.error("Media concatenation failed with return code %d:\n%s", rcode, outs)
            return False

        # Now we remove the file list file:
        logger.debug("Done concatenating %d media files.", len(files))
        return True

    def compose_video(self, vfile, afile):
        """Compose a video file adding a given audio file in background."""
        # logger.info("Should compose '%s' into '%s'", afile, vfile)

        if ".rush." in vfile:
            dst_file = vfile.replace(".rush", ".final")
        else:
            dst_file = self.set_path_extension(vfile, ".final.mkv")

        # Put the final file in our current folder:
        folder = self.get_cwd()
        dst_file = self.get_path(folder, self.get_filename(dst_file))

        my_clip = mpe.VideoFileClip(vfile)
        video_dur = my_clip.duration

        my_audio = mpe.AudioFileClip(afile)
        audio_dur = my_audio.duration

        # Fadding duration:
        fade_dur = 5

        # logger.info("Video duration is: %s", video_dur)

        # Reference code:

        # ffmpeg -i video.mp4 -i music.mp3 -filter_complex "[0:a]aformat=fltp:44100:stereo,volume=0.8[a0];
        #    [1:a]aformat=fltp:44100:stereo,volume=0.6[a1];
        #    [a0][a1]amix=inputs=2:duration=first:dropout_transition=3"
        #    -c:v copy -y output.mp4

        # Ffmpeg fade-in/fade-out effect:

        # ffmpeg -i input1.mp3 -i input2.mp3 -filter_complex "[0:a]afade=t=in:st=0:d=5,afade=t=out:st=15:d=5[a1];
        #     [1:a]afade=t=in:st=10:d=5,afade=t=out:st=20:d=5[a2];
        #     [a1][a2]amix=inputs=2" -c:a aac -b:a 256k output.mp3

        tools: ToolsManager = self.get_component("tools")
        ffmpeg_path = tools.get_tool_path("ffmpeg")
        # logger.info("FFmpeg tool path is: %s", ffmpeg_dir)

        end_delay = int((video_dur - 25.0) * 1000.0)

        # filter_str = "[0:a]aformat=fltp:44100:stereo,volume=2.0,loudnorm=I=-18:TP=-1.7:LRA=10[a0];"
        # filter_str += "[a0]highpass=f=200,lowpass=f=3000[a0b];"
        filter_str = "[0:a]aformat=fltp:44100:stereo,volume=2.0[a0];"
        filter_str += "[1:a]aformat=fltp:44100:stereo,volume=0.10[a1];"
        filter_str += "[1:a]aformat=fltp:44100:stereo,volume=0.12[a1b];"
        filter_str += (
            f"[a1]afade=t=in:st=0:d={fade_dur},afade=t=out:st={min(audio_dur-20, 60-fade_dur)}:d={fade_dur*2.0}[a2];"
        )
        filter_str += f"[a1b]afade=t=in:st=0:d={fade_dur*2.0}[a3];"
        filter_str += f"[a3]adelay=delays={end_delay}:all=1[a4];"
        filter_str += "[a0][a2][a4]amix=inputs=3:duration=first:dropout_transition=3"

        cmd = [ffmpeg_path, "-threads", "8", "-i", vfile, "-i", afile]
        cmd += ["-filter_complex", f"{filter_str}"]
        cmd += ["-c:v", "copy", "-y", dst_file]

        logger.info("Executing command: %s", cmd)
        res, rcode, outs = self.execute(cmd)

        if not res:
            logger.error("Video composition failed with return code %d:\n%s", rcode, outs)
            return False

        # my_clip = mpe.VideoFileClip(vfile)
        # audio_background = mpe.AudioFileClip(afile).volumex(0.1)
        # main_audio = my_clip.audio.volumex(2.0)

        # final_audio = CompositeAudioClip([main_audio, audio_background])
        # # final_audio = main_audio + audio_background
        # final_clip = my_clip.set_audio(final_audio)

        # logger.info("Writting video file: %s", dst_file)
        # # final_clip.write_videofile(dst_file, codec="mpeg4")
        # final_clip.write_videofile(dst_file, codec="libx264", fps=my_clip.fps, preset="slower")
        # final_clip.write_videofile(dst_file, ffmpeg_params=["-c:v", "copy"])

        logger.info("Done writting file.")
        return True

    def get_movie_resolution_ffmpeg(self, fpath):
        """Retrieve a movie file resolution using ffmpeg"""

        try:
            probe = ffmpeg.probe(fpath)
            video_streams = [stream for stream in probe["streams"] if stream["codec_type"] == "video"]

            # Should have 1 video stream:
            nstreams = len(video_streams)
            assert nstreams >= 1, f"Invalid number of video streams: {nstreams}"
            ww = video_streams[0]["width"]
            hh = video_streams[0]["height"]
            return True, ww, hh
        except ffmpeg._run.Error:
            return False, 0, 0

    def get_movie_resolution_clip(self, fpath):
        """Retrieve a movie file resolution using pymovie"""

        try:
            clip = mpe.VideoFileClip(fpath)
            return True, clip.w, clip.h
        except (UnicodeDecodeError, OSError):
            return False, 0, 0

    def get_movie_resolution(self, fpath):
        """Get movie resolution"""
        res, ww, hh = self.get_movie_resolution_ffmpeg(fpath)
        if res:
            return ww, hh

        res, ww, hh = self.get_movie_resolution_clip(fpath)
        if res:
            return ww, hh

        logger.warning("Cannot retrieve resolution of movie file %s", fpath)
        return 0, 0

    def classify_movies(self):
        """Classify our movies"""

        # get the movies_dir:
        movies_dir = self.ctx.select_first_valid_path(self.config["movies_dir"])

        if movies_dir is None:
            logger.info("No valid movies folder.")
            return

        # Collect all the files available in this directory:
        # Only process the movie files that are in the temp folder:
        tmp_dir = self.get_path(movies_dir, "temp")
        if not self.dir_exists(tmp_dir):
            logger.info("No movie file to classify.")
            return

        all_files = self.get_all_files(tmp_dir, recursive=True)
        nfiles = len(all_files)
        logger.info("Found %d files.", nfiles)

        # List all the extensions of those files:
        # exts = set()
        # for fname in all_files:
        #     parts = os.path.splitext(fname)
        #     if parts[1] != "":
        #         exts.add(parts[1])

        # exts = list(exts)
        # logger.info("Found file extensions: %s", exts)

        movie_exts = [".mkv", ".avi", ".mp4", ".flv"]
        for fname in all_files:
            parts = os.path.splitext(fname)
            ext = parts[1]
            if ext in movie_exts:
                fpath = self.get_path(tmp_dir, fname)
                # logger.info("Processing file: %s", fpath)

                # Get the size of that movie file:
                ww, hh = self.get_movie_resolution(fpath)
                logger.info("Movie %s: %dx%d", fname, ww, hh)

                # select the resolution folder where we should place that file:
                if ww == 0:
                    folder = "Unknown"
                elif ww >= 3840:
                    folder = "4K"
                elif ww >= 1920:
                    folder = "1080p"
                elif ww >= 1280:
                    folder = "720p"
                else:
                    folder = "SD"

                # Move the file into the correct folder:
                src_file = self.get_path(tmp_dir, fname)
                dst_file = self.get_path(movies_dir, folder, fname)

                parent_dir = self.get_parent_folder(dst_file)
                self.make_folder(parent_dir)

                self.move_path(src_file, dst_file)

                # Check if we have an srt file:
                srt_file = self.set_path_extension(src_file, ".srt")
                if self.file_exists(srt_file):
                    logger.info("Moving srt file %s", srt_file)
                    dst_file = self.set_path_extension(dst_file, ".srt")
                    self.move_path(srt_file, dst_file)

            else:
                logger.info("Ignoring file %s (ext='%s')", fname, ext)

        # finally we list all the folders in the temp dir:
        folders = self.get_all_folders(tmp_dir, recursive=True)
        # logger.info("Found folders: %s", self.pretty_print(folders))

        folders.reverse()
        for fname in folders:
            fpath = self.get_path(tmp_dir, fname)
            if self.is_folder_empty(fpath):
                logger.info("Removing empty temp folder %s", fname)
                self.remove_folder(fpath)

    def find_silences(self, input_file, sthres, mindur, minspeech):
        """Find the silences in a given input file."""
        # folder = self.get_parent_folder(input_file)
        out_file = self.set_path_extension(input_file, "_silences.json")
        # self.info("Should write silence files %s", out_file)
        self.info("Detecting silences in %s...", input_file)
        segs = self.detect_segments_to_keep(input_file, sthres, mindur, minspeech)

        self.info("Writing %d speech segments in %s.", len(segs), out_file)
        self.write_json(segs, out_file)

    def cut_silences(self, input_file, seg_file):
        """Remove silences from input file."""
        ext = self.get_path_extension(input_file)
        out_file = self.set_path_extension(input_file, f"_cleaned{ext}")

        tools: ToolsManager = self.get_component("tools")
        ffmpeg_path = tools.get_tool_path("ffmpeg")
        # folder = self.get_parent_folder(ffmpeg_path)
        # ffprobe_path = self.get_path(folder, "ffprobe.exe")

        # os.environ["FFMPEG_BINARY"] = ffmpeg_path
        # os.environ["FFPROBE_BINARY"] = ffprobe_path

        # try:
        #     probe = ffmpeg.probe("test", cmd=ffmpeg_path)
        # except FileNotFoundError:
        #     print("FFmpeg not found at the specified path")
        #     return
        # except:
        #     print("FFmpeg found and working")

        self.info("Removing silences from %s...", input_file)
        segments = self.read_json(seg_file)

        batch_size = 50
        temp_files = []

        folder = self.get_parent_folder(input_file)
        temp_dir = self.get_path(folder, "ffmpeg_files")

        self.make_folder(temp_dir)

        # Process segments in batches
        for batch_start in range(0, len(segments), batch_size):
            batch_segments = segments[batch_start : batch_start + batch_size]

            # Create temporary file for this batch
            temp_file = self.get_path(temp_dir, f"chunk_{len(temp_files)}.mkv")
            temp_files.append(temp_file)

            # Process this batch
            input_stream = ffmpeg.input(input_file)  # NO cmd parameter here
            segment_streams = []

            for segment in batch_segments:
                start_time = segment["start"]
                duration = segment["end"] - segment["start"]

                video_seg = input_stream.video.filter("trim", start=start_time, duration=duration).filter(
                    "setpts", "PTS-STARTPTS"
                )
                audio_seg = input_stream.audio.filter("atrim", start=start_time, duration=duration).filter(
                    "asetpts", "PTS-STARTPTS"
                )

                segment_streams.append([video_seg, audio_seg])

            # Concatenate this batch
            if len(segment_streams) > 1:
                video_streams = [seg[0] for seg in segment_streams]
                audio_streams = [seg[1] for seg in segment_streams]

                # NO cmd parameter in filter calls
                concat_video = ffmpeg.filter(video_streams, "concat", n=len(video_streams), v=1, a=0)
                concat_audio = ffmpeg.filter(audio_streams, "concat", n=len(audio_streams), v=0, a=1)

                # NO cmd parameter in output call
                # Note: cannot jsut copy the streams here.
                batch_output = ffmpeg.output(concat_video, concat_audio, temp_file, vcodec="libx264", acodec="aac")
                # batch_output = ffmpeg.output(concat_video, concat_audio, temp_file, vcodec="copy", acodec="copy")
            else:
                video_seg, audio_seg = segment_streams[0]
                # NO cmd parameter in output call
                batch_output = ffmpeg.output(video_seg, audio_seg, temp_file, vcodec="libx264", acodec="aac")
                # batch_output = ffmpeg.output(video_seg, audio_seg, temp_file, vcodec="copy", acodec="copy")

            # Add error handling and verbose output
            try:
                # First, let's see what command will be executed
                # cmd = ffmpeg.compile(batch_output)
                # self.info("FFmpeg command: %s", " ".join(cmd))

                # ONLY use cmd parameter with ffmpeg.run()
                ffmpeg.run(batch_output, overwrite_output=True, quiet=False, cmd=ffmpeg_path)
                self.info(
                    f"Processed batch {batch_start//batch_size + 1}/{(len(segments) + batch_size - 1)//batch_size}"
                )

            except ffmpeg.Error as e:
                self.error("FFmpeg error occurred:")
                self.error("stdout: %s", e.stdout.decode("utf-8") if e.stdout else "None")
                self.error("stderr: %s", e.stderr.decode("utf-8") if e.stderr else "None")
                raise

        # Concatenate all batch files
        if len(temp_files) > 1:
            # Concat the media files:
            self.concat_media(temp_files, out_file)

            # # NO cmd parameter in input calls
            # input_streams = [ffmpeg.input(temp_file) for temp_file in temp_files]
            # video_streams = [stream.video for stream in input_streams]
            # audio_streams = [stream.audio for stream in input_streams]

            # # NO cmd parameter in filter calls
            # final_video = ffmpeg.filter(video_streams, "concat", n=len(video_streams), v=1, a=0)
            # final_audio = ffmpeg.filter(audio_streams, "concat", n=len(audio_streams), v=0, a=1)

            # # NO cmd parameter in output call
            # # final_output = ffmpeg.output(final_video, final_audio, out_file, vcodec="libx264", acodec="aac")
            # final_output = ffmpeg.output(final_video, final_audio, out_file, vcodec="copy", acodec="copy")

            # try:
            #     # ONLY use cmd parameter with ffmpeg.run()
            #     ffmpeg.run(final_output, overwrite_output=True, quiet=False, cmd=ffmpeg_path)
            # except ffmpeg.Error as e:
            #     self.error("FFmpeg final concatenation error:")
            #     self.error("stdout: %s", e.stdout.decode("utf-8") if e.stdout else "None")
            #     self.error("stderr: %s", e.stderr.decode("utf-8") if e.stderr else "None")
            #     raise
        else:
            # Just rename the single temp file
            os.rename(temp_files[0], out_file)
            temp_files.remove(temp_files[0])

        self.info(f"Final video saved to: {out_file}")

        # Clean up temporary files
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                self.info("Removing temp file %s", temp_file)
                os.remove(temp_file)

        if os.path.exists(temp_dir):
            self.remove_folder(temp_dir)

    def detect_segments_to_keep(
        self, audio_path, silence_threshold=-40, min_silence_duration=0.5, min_speech_duration=0.5
    ):
        """Detect silences."""
        # Load audio
        y, sr = librosa.load(audio_path)

        # Calculate RMS energy
        rms = librosa.feature.rms(y=y)[0]

        # Convert to dB
        rms_db = librosa.amplitude_to_db(rms)

        self.info("Using silence threshold: %fdB", silence_threshold)
        self.info("Using silence min duration: %fsecs", min_silence_duration)

        self.info(f"RMS dB range: {rms_db.min():.1f} to {rms_db.max():.1f}")
        self.info(f"RMS dB mean: {rms_db.mean():.1f}")
        self.info(f"RMS dB median: {np.median(rms_db):.1f}")

        # Detect speech frames
        speech_frames = rms_db > silence_threshold

        ratio = np.count_nonzero(speech_frames) / rms_db.size
        self.info("Speech ratio is: %.3f%%", ratio * 100.0)

        # Convert frame indices to time
        frame_times = librosa.frames_to_time(np.arange(len(speech_frames)), sr=sr)

        # Find speech segments
        segments_to_keep = []
        in_speech = False
        start_time = None

        for i, has_speech in enumerate(speech_frames):
            current_time = frame_times[i]

            if has_speech and not in_speech:
                # Start of speech segment
                start_time = current_time
                in_speech = True

            elif not has_speech and in_speech:
                # End of speech segment - but check if silence is long enough
                # Look ahead to see when speech resumes
                silence_start = current_time
                silence_end = None

                # Find the end of this silence period
                for j in range(i + 1, len(speech_frames)):
                    if speech_frames[j]:
                        silence_end = frame_times[j]
                        break

                if silence_end is None:
                    # Silence continues to end of file
                    segments_to_keep.append({"start": float(start_time), "end": float(silence_start)})
                    in_speech = False
                else:
                    # Check if silence is long enough to split segments
                    silence_duration = silence_end - silence_start
                    if silence_duration >= min_silence_duration:
                        # Long silence - end current segment
                        segments_to_keep.append({"start": float(start_time), "end": float(silence_start)})
                        in_speech = False
                    # If silence is short, we continue the current segment

        # Handle case where file ends during speech
        if in_speech and start_time is not None:
            segments_to_keep.append({"start": float(start_time), "end": float(frame_times[-1])})

        # Compute total duration of the non silence:
        dur = 0.0
        dcount = 0
        final_segments = []
        for seg in segments_to_keep:
            sdur = seg["end"] - seg["start"]
            if sdur > min_speech_duration:
                dur += sdur
                final_segments.append(seg)
            else:
                dcount += 1
                # self.info("Discarding too short speech segment of %.3f secs", sdur)

        if dcount > 0:
            self.info("Discarding %d too short speech segments (< %.2f secs)", dcount, min_speech_duration)

        self.info("Total speech duration: %.2f mins", dur / 60.0)

        return final_segments

    def is_video_file(self, filename):
        """Check if a file is a video file."""
        ext = self.get_path_extension(filename).lower()
        return ext in [".mkv", ".mp4"]

    def preprocess_rushes(self, sthres, mindur, minspeech):
        """Method used to preprocess all the available rushes."""
        # Find all the mkv/mp4 files in the current folder:
        folder = self.get_cwd()
        self.info("Processing files in %s", folder)
        all_files = self.get_all_files(folder)
        # self.info("Found files %s", all_files)

        video_files = [self.get_path(folder, file) for file in all_files if self.is_video_file(file)]
        self.make_folder("processed")

        def has_cleaned(flist):
            for fname in flist:
                if "_cleaned." in fname:
                    return True

            return False

        def select_sound_source(flist):
            selected = flist[0]
            for fname in flist:
                if "_cleaned" in fname or "_centered" in fname:
                    continue
                selected = fname
            return selected

        def select_centered_file(flist):
            for fname in flist:
                if "_centered" in fname:
                    return fname
            return None

        # We expect the videos to come with the "partX_" prefix
        part_idx = 1
        while True:
            prefix = f"part{part_idx}_"
            webcam_prefix = f"{prefix}webcam_"
            mainscreen_prefix = f"{prefix}mainscreen_"
            webcam_files = [file for file in video_files if self.get_filename(file).startswith(webcam_prefix)]
            screen_files = [file for file in video_files if self.get_filename(file).startswith(mainscreen_prefix)]

            # If we have no file for this part we stop here:
            if len(webcam_files) == 0 and len(screen_files) == 0:
                break

            # if both are already cleaned, we move to the next part.
            if has_cleaned(webcam_files) and has_cleaned(screen_files):
                self.info("Part %d already cleaned.", part_idx)
                part_idx += 1
                continue

            # We need to perform the processing so we need the silence json file:
            sound_src = select_sound_source(webcam_files)

            # Extrat the audio:
            self.info("Extracting audio from %s...", sound_src)
            self.extract_audio(sound_src, "mp3")

            audio_file = f"{sound_src}.mp3"

            # Extract the silences:
            self.info("Detecting silences from %s...", audio_file)
            self.find_silences(audio_file, sthres, mindur, minspeech)

            seg_file = self.set_path_extension(audio_file, "_silences.json")

            # Now find the centered webcam file:
            if not has_cleaned(webcam_files):
                # Check if we have the centered webcam file:
                centered_file = select_centered_file(webcam_files)
                if centered_file is None:
                    self.check(len(webcam_files) == 1, "Expected only one file in list: %s", webcam_files)
                    vfile = webcam_files[0]
                    self.process_webcam_view(vfile)
                    dstfile = self.get_path(folder, "processed", self.get_filename(vfile))
                    self.move_path(vfile, dstfile)

                self.info("Removing silences from %s...", centered_file)
                self.cut_silences(centered_file, seg_file)

                dstfile = self.get_path(folder, "processed", self.get_filename(centered_file))
                self.move_path(centered_file, dstfile)

            if not has_cleaned(screen_files):
                self.check(len(screen_files) == 1, "Expected only one file in list: %s", screen_files)
                vfile = screen_files[0]
                self.info("Removing silences from %s...", vfile)
                self.cut_silences(vfile, seg_file)

                dstfile = self.get_path(folder, "processed", self.get_filename(vfile))
                self.move_path(vfile, dstfile)

            # cleanup:
            self.remove_file(seg_file)
            self.remove_file(audio_file)

            # Move to the next part:
            part_idx += 1

        self.info("Done processing %d rush parts.", part_idx - 1)


if __name__ == "__main__":
    # Create the context:
    context = NVPContext()

    # Add our component:
    comp = context.register_component("MovieHandler", MovieHandler(context))

    psr = context.build_parser("classify-movies")
    # psr.add_flag("-f", "--use-folder-name", dest="use_folder_name")("Rename using parent folder name")
    # psr.add_str("--input", dest="input_folder")("Input folder to start the renaming.")
    psr = context.build_parser("compose")
    psr.add_str("-i", "--input", dest="input_file")("input video file to use as base.")
    psr.add_str("-a", "--add-audio", dest="add_audio")("additional audio stream to add in the video.")

    psr = context.build_parser("concat-media")
    psr.add_str("-i", "--inputs", dest="input_files")("input video files to concatenate")
    psr.add_str("-o", "--output", dest="output_file")("Output file to generate.")

    psr = context.build_parser("cut-media")
    psr.add_str("-i", "--input", dest="input_file")("input video file to cut")
    psr.add_str("-d", "--duration", dest="duration")("Duration to keep")
    psr.add_str("-s", "--start", dest="start_time", default="00:00:00")("Start time of the section to keep")

    psr = context.build_parser("split-media")
    psr.add_str("-i", "--input", dest="input_file")("input video file to split")
    psr.add_str("-d", "--duration", dest="duration")("Duration to keep")

    psr = context.build_parser("rescale-media")
    psr.add_str("-i", "--input", dest="input_file")("input video file to scale")
    psr.add_str("-s", "--scale", dest="scale")("output size to use in format: 1920:1080")

    psr = context.build_parser("norm-sound")
    psr.add_str("-i", "--input", dest="input_file")("input video file to normalize")
    psr.add_str("-o", "--output", dest="output_file")("Output file to generate.")
    psr.add_float("-g", "--gain", dest="gain", default=1.0)("Volume gain factor")

    psr = context.build_parser("extract-audio")
    psr.add_str("-i", "--input", dest="input_file")("input video file to normalize")
    psr.add_str("-f", "--format", dest="format", default="mp3")("Format to use for the output can be mp3 or wav")

    psr = context.build_parser("add-video-dates")

    psr = context.build_parser("process-webcam-view")
    psr.add_str("-i", "--input", dest="input_file")("Input file where to process the webcam view")

    psr = context.build_parser("find-silences")
    psr.add_str("-i", "--input", dest="input_file")("Input file to process")
    psr.add_float("-t", "--threshold", dest="silence_threshold", default=-75)("Silence threshold.")
    psr.add_float("-d", "--min-dur", dest="min_silence_duration", default=0.5)("Silence min duration.")
    psr.add_float("-s", "--min-speech", dest="min_speech_duration", default=1.0)("Speech min duration.")

    psr = context.build_parser("cut-silences")
    psr.add_str("-i", "--input", dest="input_file")("Input file to process")
    psr.add_str("-s", "--segments", dest="seg_file")("Segment file")

    psr = context.build_parser("preprocess-rushes")
    psr.add_float("-t", "--threshold", dest="silence_threshold", default=-75)("Silence threshold.")
    psr.add_float("-d", "--min-dur", dest="min_silence_duration", default=0.5)("Silence min duration.")
    psr.add_float("-s", "--min-speech", dest="min_speech_duration", default=1.0)("Speech min duration.")

    comp.run()
