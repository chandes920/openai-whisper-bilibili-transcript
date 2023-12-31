import math
import os
os.environ["IMAGEIO_FFMPEG_EXE"] = "/opt/homebrew/bin/ffmpeg"
os.environ["IMAGEMAGICK_BINARY"] = "/opt/homebrew/bin/convert"

from faster_whisper import WhisperModel
from moviepy.editor import TextClip, VideoFileClip, CompositeVideoClip
from moviepy.video.tools.subtitles import SubtitlesClip
import pandas as pd
import pickle

from utils import (
    mp4_duration,
    split_mp4,
    combine_outputs,
    create_working_dir,
    delete_working_files,
    load_pkl,
    write_pkl
)


class OpenAIWhisperTranscription:
    def __init__(
        self,
        mp4_name: str,
        create_new_dir: bool=True
    ):

        file_name = mp4_name.rstrip(".mp4")
        if create_new_dir:
            create_working_dir(file_name, mp4_name)
        current_dir = os.getcwd()
        self.new_path = os.path.join(current_dir, file_name)
        self.mp4 = os.path.join(self.new_path, f"{file_name}.mp4")

        self.file_path = self.mp4.strip(".mp4")

        self.video_list=[self.mp4]
        self.output_list=[f"{self.mp4}_output.mp4"]

    def split_mp4_to_parts(self, duration_per_split: int = 600):
        total_duration = mp4_duration(self.mp4)
        num_splits = math.ceil(total_duration / duration_per_split)

        video_list = []

        for i in range(1, 1 + num_splits):
            start = (i - 1) * duration_per_split
            duration = min(duration_per_split, math.floor(total_duration) - start)
            end = start + duration

            output_file_mp4 = f"{self.file_path}_part_{i}.mp4"
            video_list.append(output_file_mp4)
            split_mp4(self.mp4, start, end, output_file_mp4)

        self.video_list = video_list
        self.output_list = [f"{video.strip('.mp4')}_output.mp4" for video in self.video_list]

    def openai_transcribe_to_df(
        self,
        model_size: str = "large-v3",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "ja",
        beam_size: int = 5,
        task: str = "translate",
    ):
        # or run on CPU with INT8
        model = WhisperModel(model_size, device = device, compute_type = compute_type)

        result_dict = {}

        for i in self.video_list:
            segments, _ = model.transcribe(i, language=language, beam_size=beam_size, task=task)
            print(f"Transcribe generator initiated for {i}.")
            segments = list(segments)
            print(f"Transcribe completed for {i}.")
            # Extract start, end, and text from each segment
            data = {
                "start": [segment.start for segment in segments],
                "end": [segment.end for segment in segments],
                "text": [segment.text.strip() for segment in segments],
            }
            # Create a DataFrame from the extracted data
            df = pd.DataFrame(data)
            print(f"Transcribe dataframe created for {i}")

            output_pkl_file_name = i.strip(".mp4")

            with open(f"{output_pkl_file_name}.pkl", "wb") as f:
                pickle.dump(df, f)
            print(f"Transcribe pkl stored for {i}")

            result_dict[i] = df
        return result_dict

    def create_subs_dict(self, result_dict: dict):
        subs_dict = {}

        for i in self.video_list:
            subs = []
            for _, row in result_dict[i].iterrows():
                start = row["start"]
                end = row["end"]
                text = row["text"]
                subs.append(((start, end), text))
                subs_dict[i] = subs

        with open(f"{self.new_path}/subs_dict.pkl", "wb") as f:
            pickle.dump(subs_dict, f)

        return subs_dict

    def add_subs_to_video(
        self,
        subs_dict: dict,
        font: str = "arial-bold",
        fontsize: int = 45,
        color: str = "white",
        stroke_color: str = "black",
        stroke_width: float = 3,
        size: tuple = (1100, 720),
        method: str = "caption",
        align: str = "South"
    ):
        generator = lambda txt: TextClip(txt, font=font, fontsize=fontsize, color=color, stroke_color=stroke_color, stroke_width=stroke_width, size=size, method=method, align=align)

        for i in self.video_list:
            subtitles = SubtitlesClip(subs_dict[i], generator)
            video = VideoFileClip(i)
            result = CompositeVideoClip(
                [video, subtitles.set_pos(("center", "bottom"))]
            )
            output_video_file_name = i.strip(".mp4")
            result.write_videofile(
                f"{output_video_file_name}_output.mp4",
                fps=video.fps,
                temp_audiofile=f"temp-audio.m4a",
                remove_temp=True,
                codec="libx264",
                audio_codec="aac",
            )

    def combine_all_parts(self):
        combine_outputs(self.file_path, self.output_list)

    def load_pkl(self, pkl_file_name):
        object = load_pkl(f"{self.new_path}/{pkl_file_name}.pkl")
        return object

    def write_pkl(self, object, pkl_file_name):
        write_pkl(object, f"{self.new_path}/{pkl_file_name}.pkl")