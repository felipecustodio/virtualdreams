# -*- coding: utf-8 -*-

"""vapor.py: Virtual Dreams Bot for Telegram. Generates Vaporwave music."""

__author__  = "Felipe S. Custódio"
__license__ = "GPL"
__credits__ = ["felipecustodio","WJLiddy","vivjay"]

# environment
import os
import sys
from threading import Thread
from pathlib import Path
from dotenv import load_dotenv
import logging
from datetime import datetime
import time
from timeit import default_timer as timer
# bot api
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
import re
import urllib.request
import urllib.parse
import youtube_dl

# logging
import logzero
from logzero import logger
from logzero import setup_logger

logzero.logfile("log.log", maxBytes=1e6, backupCount=5)
stats = setup_logger(name="stats", logfile="requests.log", level=logging.INFO, maxBytes=1e6, backupCount=5)

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

# video duration limit
MAX_DURATION = 420  # seconds (7 minutes)

# youtube urls for query parsing
youtube_urls = ('youtube.com', 'https://www.youtube.com/', 'http://www.youtube.com/', 'http://youtu.be/', 'https://youtu.be/', 'youtu.be')

# emojis
emoji_palm_tree = emojize(":palm_tree:", use_aliases=True)
emoji_video_camera = emojize(":video_camera:", use_aliases=True)
emoji_cd = emojize(":cd:", use_aliases=True)

# bot messages
error_str = emoji_cd + " ＥＲＲＯＲ.\nSomething went wrong!\nAn error has occurred or a song name or link wasn't provided.\nPlease try again!"
working_str = emoji_palm_tree + " ＷＯＲＫＩＮＧ．．．\nThis can take up a bit more than a minute. Sit back and relax. If you don't hear back from me, try again!"
help_str = emoji_palm_tree + " Ｗｅｌｃｏｍｅ ｔｏ Ｖｉｒｔｕａｌ Ｄｒｅａｍｓ. " + emoji_palm_tree + "\n\nＨＯＷ ＴＯ ＵＳＥ:\n" + emoji_cd + " /vapor \"song name\"\n" + emoji_video_camera + " /vapor YouTube URL.\n\nWorks with videos between 5 seconds and 7 minutes.\n\nIf your request is taking too long, please try again.\n"
unknown_str = emoji_cd + " ＥＲＲＯＲ.\nThis is not a valid command. Use /help to find out more."


def vapor(query, bot, request_id, chat_id):
    """Returns audio to the vapor command handler

    Searches YouTube for 'query', finds first match that has
    duration under the limit, download video with youtube_dl
    and extract .wav audio with ffmpeg. Extract chorus using
    pychorus. If it fails, try smaller chorus' times.
    Using sox, slow down and apply reverb. 
    Return vaporwaved audio.

    Query can be YouTube link. 
    """
    ydl_opts = {
        'quiet': 'True',
        'format': 'bestaudio/best',
        'outtmpl': str(request_id) +'.%(ext)s',
        'prefer_ffmpeg': 'True', 
        'noplaylist': 'True',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
    }

    logger.info("[" + str(request_id) + "] " + "Got request!")
    logger.debug("[" + str(request_id) + "] " + str(query) + " " + str(chat_id))

    # prepare audio files paths (for all systems)
    logger.info("[" + str(request_id) + "] " + "Preparing audio paths...")
    original_path = str(request_id) + ".wav"
    chorus_path = str(request_id) + "_chorus.wav"
    vapor_path = str(request_id) + "_vapor.wav"
    logger.debug("[" + str(request_id) + "] " + " " + str(original_path) + " " + str(chorus_path) + " " + str(vapor_path))

    logger.info("[" + str(request_id) + "] " + "Sending 'Working' message to " + str(chat_id) + '...')
    try:
        bot.send_message(chat_id=chat_id, text=working_str)
    except Exception as e:
        logger.error("[" + str(request_id) + "] " + e)
        raise ValueError('Could not send message to user ' + str(chat_id))

    # check if query is youtube url
    if not query.lower().startswith((youtube_urls)):
        logger.info("[" + str(request_id) + "] " + "Searching for YouTube videos...")
        # search for youtube videos matching query
        query_string = urllib.parse.urlencode({"search_query" : query})
        html_content = urllib.request.urlopen("http://www.youtube.com/results?" + query_string)
        search_results = re.findall(r'href=\"\/watch\?v=(.{11})', html_content.read().decode())
        info = False

        # find video that fits max duration
        logger.info("[" + str(request_id) + "] " + "Get video information...")
        for url in search_results:
            # check for video duration
            try:
                info = youtube_dl.YoutubeDL(ydl_opts).extract_info(url,download = False)
            except Exception as e:
                logger.error("[" + str(request_id) + "] " + e)
                raise ValueError('Could not get information about video.')
            full_title = info['title']
            if (info['duration'] < MAX_DURATION and info['duration'] >= 5):
                # get first video that fits the limit duration
                logger.debug("[" + str(request_id) + "] " + "Got video: " + str(full_title))
                break
        
        # if we ran out of urls, return error
        if (not info):
            raise ValueError('Could not find a video.')

    # query was a youtube link
    else:
        logger.info("[" + str(request_id) + "] " + "Query was a YouTube URL.")
        url = query
        info = youtube_dl.YoutubeDL(ydl_opts).extract_info(url,download = False)
        # check if video fits limit duration
        if (info['duration'] < 5 or info['duration'] > MAX_DURATION):
            raise ValueError('Video is too short. Need 5 seconds or more.')

    # cleanup title
    title = (re.sub(r'\W+', '', info['title']))[:15]
    title = str((title.encode('ascii',errors='ignore')).decode())

    # check if cached audio exists
    logger.info("[" + str(request_id) + "] " + "Checking if cached audio exists...")
    vapor_path = title + "_vapor.wav"
    if Path(vapor_path).is_file():
        vapor_path = title + "_vapor.wav"
        try:
            bot.send_audio(chat_id=chat_id, audio=open(vapor_path, 'rb'))
        except Exception as e:
            logger.error("[" + str(request_id) + "] " + e)
            raise ValueError('Failed to send audio.')
        return 

    # download video and extract audio
    logger.info("[" + str(request_id) + "] " + "Downloading video...")
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
        except Exception as e:
            logger.error("[" + str(request_id) + "] " + e)
            raise ValueError('Could not download ' + str(full_title) + '.')

    # find and extract music chorus
    logger.info("[" + str(request_id) + "] " + "Searching for chorus...")
    chorus = False
    chorus_duration = 15 # anything bigger would consume too much memory
    while (not chorus and chorus_duration > 0):
        chorus = find_and_output_chorus(original_path, chorus_path, 15)
        chorus_duration -= 5
    
    if (not chorus):
        logger.info("[" + str(request_id) + "] " + "Could not find chorus, using first segment...")
        # could not find chorus, use first seconds instead
        chorus_duration = 15 # reset durations
        try:
            song = AudioSegment.from_wav(original_path)
        except Exception as e:
            logger.error("[" + str(request_id) + "] " + e)
            raise ValueError('Failed to get chorus audio segment.')
        
        # get the smallest possible segment
        # video is already guaranteed to be equal or greater than 5 seconds
        while (chorus_duration > info['duration']):
            chorus_duration -= 5

        try:
            seconds = chorus_duration * 1000
            first_seconds = song[:seconds]
            first_seconds.export(chorus_path, format="wav")
        except Exception as e:
            logger.error("[" + str(request_id) + "] " + e)
            raise ValueError('Failed to export chorus audio segment.')

    # make it vaporwave (python wrapper for sox)
    vapor_path = str(title) + "_vapor.wav"
    
    infile = str(chorus_path)
    outfile = str(vapor_path)

    logger.debug("[" + str(request_id) + "] " + str(infile) + " " + str(outfile))
    try:
        logger.info("[" + str(request_id) + "] " + "Applying Vaporwave SFX...")
        fx(infile, outfile)
    except Exception as e:
        logger.error("[" + str(request_id) + "] " + e)
        raise ValueError('Failed to apply Vaporwave SFX.')
    except:
        logger.error("[" + str(request_id) + "] " + "Unexpected error:", sys.exc_info()[0])

    # send audio to user
    logger.info("[" + str(request_id) + "] " + 'Sending final audio to ' + str(chat_id) + '...')
    try:
        bot.send_audio(chat_id=chat_id, audio=open(vapor_path, 'rb'))
    except Exception as e:
        logger.error("[" + str(request_id) + "] " + e)
        raise ValueError('Failed to send audio.')

    # cleanup
    try:
        os.remove(original_path)
        os.remove(chorus_path)
    except OSError as e:
        logger.error("[" + str(request_id) + "] " + e)
        pass


# bot handlers
@run_async
def help_command(bot, update):
    """ /help - Shows usage """
    bot.send_message(chat_id=update.message.chat_id, text=help_str)


@run_async
def vapor_command(bot, update):
    """ /vapor - Request handler """
    request_date = time.strftime("%Y%m%d-%H%M%S")

    request_id = update.message.message_id
    username = str(bytes(str(update.message.from_user.username), 'utf-8').decode('utf-8', 'ignore'))
   
    request_text = update.message.text.replace('/vapor ','')
    request_text = str(bytes(str(request_text), 'utf-8').decode('utf-8', 'ignore'))

    chat_id = update.message.chat_id
    status = "success"

    try:
        start = timer()
        vapor(request_text, bot, request_id, chat_id)
    except ValueError as e:
        logger.error("[" + str(request_id) + "] " + e)
        status = "failed"
        bot.send_message(chat_id=chat_id, text=error_str)
    finally:
        end = timer()
        elapsed = str(end - start)
        logger.info("[" + str(request_id) + "] " + "Finished.")
        stats.info("{},{},{},{},{},{}".format(request_date, str(request_id), str(username), str(request_text), str(status), str(elapsed)))


@run_async
def unknown_command(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text=unknown_str)


def main():
    # set env variables
    logger.info("VIRTUAL DREAMS TURNING ON...")
    load_dotenv()
    BOT_TOKEN = os.getenv("TOKEN")
    HEROKU_NAME = "virtualdreamsbot"
    PORT = int(os.environ.get('PORT', '8443'))

    logger.info("Dispatching workers...")
    updater = Updater(token=BOT_TOKEN, workers=2)
    dispatcher = updater.dispatcher

    # define bot handlers
    help_handler = CommandHandler('help', help_command)
    start_handler = CommandHandler('start', help_command)
    vapor_handler = CommandHandler('vapor', vapor_command)
    unknown_handler = MessageHandler(Filters.command, unknown_command)

    # start bot handlers
    logger.info("Starting handlers...")
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(vapor_handler)
    dispatcher.add_handler(unknown_handler)

    # move working directory to cache
    logger.info("Setting working directory...")
    if not os.path.exists("cache") and not (str(os.path.basename(os.getcwd())) == "cache"):
        try:
            os.makedirs("cache")
            os.chdir("cache")
        except OSError as e:
            logger.error(e)
    else:
        os.chdir("cache")

    # heroku webhook
    # updater.start_webhook(listen="0.0.0.0",
                        #   port=PORT,
                        #   url_path=BOT_TOKEN)
    # updater.bot.setWebhook("https://{}.herokuapp.com/{}".format(HEROKU_NAME, BOT_TOKEN))

    # local hosting
    logger.info("VIRTUAL DREAMS ONLINE")
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
