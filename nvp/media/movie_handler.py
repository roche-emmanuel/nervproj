"""MovieHandler handling component"""
import logging
import os

import ffmpeg

# from moviepy.editor import *
import moviepy.editor as mpe

# from moviepy.audio.AudioClip import CompositeAudioClip
from nvp.core.tools import ToolsManager
from nvp.nvp_component import NVPComponent
from nvp.nvp_context import NVPContext

logger = logging.getLogger(__name__)


class MovieHandler(NVPComponent):
    """MovieHandler component class"""

    def __init__(self, ctx: NVPContext):
        """Component constructor"""
        NVPComponent.__init__(self, ctx)

        self.config = ctx.get_config()["movie_handler"]

    def process_cmd_path(self, cmd):
        """Re-implementation of process_cmd_path"""

        if cmd == "classify-movies":
            self.classify_movies()
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

        return False

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
        filter_str += "[1:a]aformat=fltp:44100:stereo,volume=0.05[a1];"
        filter_str += "[1:a]aformat=fltp:44100:stereo,volume=0.05[a1b];"
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

    comp.run()