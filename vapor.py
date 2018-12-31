# -*- coding: utf-8 -*-

"""vapor.py: Virtual Dreams Bot for Telegram. Generates Vaporwave music."""

__author__  = "Felipe S. Custódio"
__license__ = "GPL"
__credits__ = ["WJLiddy", "vivjay"]

# environment
import os
import sys
from threading import Thread
from pathlib import Path
from dotenv import load_dotenv
# bot
from functools import wraps
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram.ext.dispatcher import run_async
from telegram import InlineQueryResultArticle, InputTextMessageContent, ChatAction
from emoji import emojize
# audio manipulation
from pysndfx import AudioEffectsChain
from pydub import AudioSegment
from pychorus import find_and_output_chorus
# youtube
import urllib.request
import urllib.parse
import re
import youtube_dl
# logging
import re
import logging
from datetime import datetime
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.FileHandler("requests.log"),
        logging.StreamHandler()
    ])
# profiling
from timeit import default_timer as timer

# youtube urls for query parsing
youtube_urls = ('youtube.com', 'https://www.youtube.com/', 'http://www.youtube.com/', 'http://youtu.be/', 'https://youtu.be/', 'youtu.be')

# video duration limit
MAX_DURATION = 420  # seconds (7 minutes)

# emojis
emoji_palm_tree = emojize(":palm_tree:", use_aliases=True)
emoji_video_camera = emojize(":video_camera:", use_aliases=True)
emoji_cd = emojize(":cd:", use_aliases=True)

# vaporwave parameters
fx = (
        AudioEffectsChain()
        .speed(0.63)
        .reverb(
               reverberance=100,
               hf_damping=50,
               room_scale=100,
               stereo_depth=100,
               pre_delay=20,
               wet_gain=0,
               wet_only=False
               )
    )


# @felup.io (bot admin)
LIST_OF_ADMINS = [71491472]


def vapor(query, bot, request_id, chat_id):
    """Returns audio to the vapor command handler

    Searches YouTube for 'query', finds first match that has
    duration under the limit, download video with youtube_dl
    and extract .mp3 audio with ffmpeg. Extract chorus using
    pychorus. If it fails, try smaller chorus' times.
    Using sox, slow down and apply reverb. 
    Return vaporwaved audio.

    Query can be YouTube link. 
    """
    # logger.info("[{}] Working on request...".format(str(request_id)))

    # check if query is youtube url
    # logger.info("[{}] Searching for query on YouTube...".format(str(request_id)))
    
    if not query.lower().startswith((youtube_urls)):
        # search for youtube videos matching query
        query_string = urllib.parse.urlencode({"search_query" : query})
        html_content = urllib.request.urlopen("http://www.youtube.com/results?" + query_string)
        search_results = re.findall(r'href=\"\/watch\?v=(.{11})', html_content.read().decode())
        info = False

        # find video that fits max duration
        for url in search_results:
            # check for video duration
            info = youtube_dl.YoutubeDL().extract_info(url,download = False)
            full_title = info['title']
            if (info['duration'] < MAX_DURATION and info['duration'] >= 5):
                # get first video that fits the limit duration
                break
        
        # if we ran out of urls, return error
        if (not info):
            raise ValueError('Could not find video.')

    # query was a youtube link
    else:
        url = query    
        info = youtube_dl.YoutubeDL().extract_info(url,download = False)
        # check if video fits limit duration
        if (info['duration'] < 5 or info['duration'] > MAX_DURATION):
            raise ValueError('Video too short!')

    # cleanup title
    title = (re.sub(r'\W+', '', info['title']))[:15]
    title = str((title.encode('ascii',errors='ignore')).decode())

    # check if cached audio exists
    vapor_path = Path(title + "_vapor.wav")
    if vapor_path.is_file():
        # logger.info("[{}] Found {} cached.".format(str(request_id), str(vapor_path)))
        vapor_path = title + "_vapor.wav"
        bot.send_audio(chat_id=chat_id, audio=open(vapor_path, 'rb'))
        return 

    # download video and extract mp3 audio
    # logger.info("[{}] Downloading audio...".format(str(request_id)))
    ydl_opts = {
        'quiet': 'True',
        'format': 'bestaudio/best',
        'outtmpl': str(request_id) +'.%(ext)s',
        'prefer-ffmpeg': 'True', 
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
        except:
            raise ValueError('Could not download ' + str(full_title) + '.')

    # prepare audio files paths (for all systems)
    root = os.getcwd()
    original_path = os.path.join(root, (str(request_id) + ".wav"))
    chorus_path = os.path.join(root, (str(request_id) + "_chorus.wav"))
    vapor_path = os.path.join(root, (str(request_id) + "_vapor.wav"))

    # find and extract music chorus
    # logger.info("[{}] Searching for song chorus...".format(str(request_id)))
    chorus = False
    chorus_duration = 15 # anything bigger would consume too much memory
    while (not chorus and chorus_duration > 0):
        chorus = find_and_output_chorus(original_path, chorus_path, 15)
        chorus_duration -= 5
    
    if (not chorus):
        # doesnt have chorus, use first seconds as chorus
        # logger.info("[{}] Chorus not found. Trying initial seconds...".format(str(request_id)))
        chorus_duration = 15 # reset durations
        song = AudioSegment.from_wav(original_path)
        
        # get the smallest possible segment
        # video is already guaranteed to be equal or greater than 5 seconds
        while (chorus_duration > info['duration']):
            chorus_duration -= 5

        seconds = chorus_duration * 1000
        first_seconds = song[:seconds]
        first_seconds.export(chorus_path, format="wav")

    # make it vaporwave (python wrapper for sox)
    vapor_path = title + "_vapor.wav"
    # logger.info("[{}] Applying Vaporwave FX.".format(str(request_id)))
    
    infile = repr(chorus_path)
    outfile = repr(vapor_path)

    fx(infile, outfile)

    # send audio to user
    # logger.info("[{}] Sending audio.".format(str(request_id), ))
    bot.send_audio(chat_id=chat_id, audio=open(vapor_path, 'rb'))

    # cleanup
    # logger.info("[{}] Cleanup temporary files.".format(str(request_id), ))
    try:
        os.remove(original_path)
        os.remove(chorus_path)
    except OSError:
        pass


# bot handlers
@run_async
def help_command(bot, update):
    """ /help - Shows usage """
    bot.send_message(chat_id=update.message.chat_id, text=emoji_palm_tree + " Ｗｅｌｃｏｍｅ ｔｏ Ｖｉｒｔｕａｌ Ｄｒｅａｍｓ. " + emoji_palm_tree + "\n\nＨＯＷ ＴＯ ＵＳＥ:\n" + emoji_cd + " /vapor \"song name\"\n" + emoji_video_camera + " /vapor YouTube URL.\n\nWorks with videos between 5 seconds and 7 minutes.\n\nIf your request is taking too long, please try again.\n")


@run_async
def vapor_command(bot, update):
    """ /vapor - Request handler """
    request_date = str(datetime.now())
    request_id = update.message.message_id
    username = str(update.message.from_user.username)
    request_text = update.message.text.replace('/vapor ','')
    chat_id = update.message.chat_id
    # logger.info("[{}] {} has requested: {}".format(str(request_id), str(username), str(request_text)))

    if (len(str(update.message.text.replace('/vapor',''))) < 5):
        # logger.error("[{}] ERROR: Query too small.".format(request_id))
        bot.send_message(chat_id=chat_id, text=emoji_cd + " ＥＲＲＯＲ.\nI need a bigger query!")
        return

    bot.send_message(chat_id=chat_id, text=emoji_palm_tree  + " ＷＯＲＫＩＮＧ．．．\nThis can take up a bit more than a minute. Sit back and relax. If you don't hear back from me, try again!")
    success = "success"
    try:
        start = timer()
        vapor(request_text, bot, request_id, chat_id)
    except ValueError as error:
        # logger.error("[{}] ERROR: {}".format(request_id, str(error)))
        success = "failed"
        bot.send_message(chat_id=chat_id, text=emoji_cd + " ＥＲＲＯＲ.\n" + str(error))
    finally:
        end = timer()
        elapsed = str(end - start)
        # logger.info("[{}] Finished request in {}s.".format(str(request_id), elapsed))
        logger.info("{},{},{},{},{},{}".format(request_date, str(request_id), str(username), str(request_text), str(success), str(elapsed)))


@run_async
def unknown_command(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text=emoji_cd + " ＥＲＲＯＲ.\nThis is not a valid command. Use /help to find out more.")


@run_async
def error_handler(bot, update, error):
    logger.warning('Update "%s" caused error "%s"', update, error)


def main():
    logger.info("Initializing...")
    
    # set env variables
    load_dotenv()
    BOT_TOKEN = os.getenv("TOKEN")
    HEROKU_NAME = "virtualdreamsbot"
    PORT = int(os.environ.get('PORT', '8443'))

    updater = Updater(token=BOT_TOKEN, workers=2)
    dispatcher = updater.dispatcher

    # define bot handlers
    help_handler = CommandHandler('help', help_command)
    start_handler = CommandHandler('start', help_command)
    vapor_handler = CommandHandler('vapor', vapor_command)
    unknown_handler = MessageHandler(Filters.command, unknown_command)

    # start bot handlers
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(vapor_handler)
    dispatcher.add_handler(unknown_handler)
    dispatcher.add_error_handler(error_handler)

    # move working directory to cache
    if not os.path.exists("cache") and not (str(os.path.basename(os.getcwd())) == "cache"):
        try:
            os.makedirs("cache")
            os.chdir("cache")
        except:
            raise
    else:
        os.chdir("cache")

    # heroku webhook
    # updater.start_webhook(listen="0.0.0.0",
                        #   port=PORT,
                        #   url_path=BOT_TOKEN)
    # updater.bot.setWebhook("https://{}.herokuapp.com/{}".format(HEROKU_NAME, BOT_TOKEN))
    logger.info("Bot ready. Working directory: {}".format(os.getcwd()))
    logger.info("date,request_id,username,request_text,success,time_elapsed")
    # local
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
