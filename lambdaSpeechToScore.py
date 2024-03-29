

import torch
import json
import os
import WordMatching as wm
import utilsFileIO
import pronunciationTrainer
import base64
import time
import audioread
import numpy as np
from torchaudio.transforms import Resample
import torchaudio
import wave
import pyaudio
import subprocess
import ffmpeg
import soundfile as sf

trainer_SST_lambda = {}
trainer_SST_lambda['en'] = pronunciationTrainer.getTrainer("en")

transform = Resample(orig_freq=48000, new_freq=16000)

def lambda_handler(real_sentence, language):
    input_file = 'hearing.wav'
    output_file = 'hearing2.wav'

    #ffmpeg.input(input_file).output(output_file, ar=16000, ac=1).run(overwrite_output=True)
    
    #input_audio = ffmpeg.input(input_file)
    #output_audio = ffmpeg.output(input_audio, output_file, ar=16000, ac=1)
    #ffmpeg.run(output_audio, overwrite_output=True)
    command1 = "/usr/bin/ffmpeg -y -i hearing.wav -ar 16000 -ac 1 hearing2.wav"
    #command1 = "ffmpeg -y -i hearing.wav -ar 16000 -ac 1 hearing2.wav"
    subprocess.run(command1, shell=True)
    command2 = "/usr/bin/mv hearing2.wav hearing.wav"
    subprocess.run(command2, shell=True )
    command3 = "python ~/milo/denoiser/denoiser.py hearing.wav hearing_output.wav"
    subprocess.run(command3,shell=True)

    recorded_audio_file = "hearing_output.wav"

    #sample_rate = 16000  # Desired sample rate
    #audio_tensor = load_audio(recorded_audio_file, sample_rate)

    #result = trainer_SST_lambda[language].processAudioForGivenText(torch.Tensor(audio_tensor), real_sentence)
    result = trainer_SST_lambda[language].processAudioForGivenText(recorded_audio_file, real_sentence)

    start = time.time()
    real_transcripts_ipa = ' '.join(
        [word[0] for word in result['real_and_transcribed_words_ipa']])
    matched_transcripts_ipa = ' '.join(
        [word[1] for word in result['real_and_transcribed_words_ipa']])

    real_transcripts = ' '.join(
        [word[0] for word in result['real_and_transcribed_words']])
    matched_transcripts = ' '.join(
        [word[1] for word in result['real_and_transcribed_words']])

    words_real = real_transcripts.lower().split()
    mapped_words = matched_transcripts.split()

    is_letter_correct_all_words = ''
    for idx, word_real in enumerate(words_real):

        mapped_letters, mapped_letters_indices = wm.get_best_mapped_words(
            mapped_words[idx], word_real)

        is_letter_correct = wm.getWhichLettersWereTranscribedCorrectly(
            word_real, mapped_letters)  # , mapped_letters_indices)

        is_letter_correct_all_words += ''.join([str(is_correct)
                                                for is_correct in is_letter_correct]) + ' '

    pair_accuracy_category = ' '.join(
        [str(category) for category in result['pronunciation_categories']])
    print('Time to post-process results: ', str(time.time()-start))

    binary_txt = is_letter_correct_all_words.split()

    for idx in range(len(mapped_words)) :
        while len(mapped_words[idx]) < len(binary_txt[idx]):
            mapped_words[idx] = mapped_words[idx] +'_'
    
    for idx, word in enumerate(words_real) :
        word = word.replace('_','')
        words_real[idx] = word

    record_txt = ' '.join(
            [word for word in words_real])

    b_txt = ' '.join(
            [word for word in binary_txt])

    words_result_html = "<div style='text-align:center;'>"
    for char_result in list(zip(record_txt, b_txt)):
        if char_result[1] == '1':
            words_result_html += "<span style= '" + "color:green;font-size:60px;" + " ' >" + char_result[0] + "</span>"
        else:
            words_result_html += "<span style= ' " + "color:red;font-size:60px;" + " ' >" + char_result[0] + "</span>"

    words_result_html += "</div>"

    res = {'recorded_transcript': result['recording_transcript'],
           'ipa_recorded_transcript': result['recording_ipa'],
           'pronunciation_accuracy': str(int(result['pronunciation_accuracy'])),
           'real_transcripts': real_transcripts, 
           'real_transcripts_ipa': real_transcripts_ipa, 
           'is_letter_correct_all_words': is_letter_correct_all_words, 
           'result_html': words_result_html}
    return res

# From Librosa

def load_audio(audio_file, sample_rate=16000):
    # Load audio file
    waveform, _ = torchaudio.load(audio_file, normalize=True)
    
    # Resample audio to the desired sample rate
    if _ != sample_rate:
        resampler = torchaudio.transforms.Resample(orig_freq=_, new_freq=sample_rate)
        waveform = resampler(waveform)
    
    return waveform


def audioread_load(path, offset=0.0, duration=None, dtype=np.float32):
    """
    Load an audio buffer using audioread.

    This loads one block at a time, and then concatenates the results.
    """

    y = []
    with audioread.audio_open(path) as input_file:
        sr_native = input_file.samplerate
        n_channels = input_file.channels

        s_start = int(np.round(sr_native * offset)) * n_channels

        if duration is None:
            s_end = np.inf
        else:
            s_end = s_start + \
                (int(np.round(sr_native * duration)) * n_channels)

        n = 0

        for frame in input_file:
            frame = buf_to_float(frame, dtype=dtype)
            n_prev = n
            n = n + len(frame)

            if n < s_start:
                # offset is after the current frame
                # keep reading
                continue

            if s_end < n_prev:
                # we're off the end.  stop reading
                break

            if s_end < n:
                # the end is in this frame.  crop.
                frame = frame[: s_end - n_prev]

            if n_prev <= s_start <= n:
                # beginning is in this frame
                frame = frame[(s_start - n_prev):]

            # tack on the current frame
            y.append(frame)

    if y:
        y = np.concatenate(y)
        if n_channels > 1:
            y = y.reshape((-1, n_channels)).T
    else:
        y = np.empty(0, dtype=dtype)

    return y, sr_native

# From Librosa


def buf_to_float(x, n_bytes=2, dtype=np.float32):
    """Convert an integer buffer to floating point values.
    This is primarily useful when loading integer-valued wav data
    into numpy arrays.

    Parameters
    ----------
    x : np.ndarray [dtype=int]
        The integer-valued data buffer

    n_bytes : int [1, 2, 4]
        The number of bytes per sample in ``x``

    dtype : numeric type
        The target output type (default: 32-bit float)

    Returns
    -------
    x_float : np.ndarray [dtype=float]
        The input data buffer cast to floating point
    """

    # Invert the scale of the data
    scale = 1.0 / float(1 << ((8 * n_bytes) - 1))

    # Construct the format string
    fmt = "<i{:d}".format(n_bytes)

    # Rescale and format the data buffer
    return scale * np.frombuffer(x, fmt).astype(dtype)


