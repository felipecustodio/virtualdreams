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

# modern caching
from cache_manager import CacheManager

logzero.logfile("log.log", maxBytes=1e6, backupCount=5)
stats = setup_logger(name="stats", logfile="requests.log", level=logging.INFO, maxBytes=1e6, backupCount=5)

# global cache manager instance
cache_manager = None

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
help_str = emoji_palm_tree + " Ｗｅｌｃｏｍｅ ｔｏ Ｖｉｒｔｕａｌ Ｄｒｅａｍｓ. " + emoji_palm_tree + "\n\nＨＯＷ ＴＯ ＵＳＥ:\n" + emoji_cd + " /vapor \"song name\"\n" + emoji_video_camera + " /vapor YouTube URL\n📊 /stats - View cache statistics\n\nWorks with videos between 5 seconds and 7 minutes.\n\nIf your request is taking too long, please try again.\n"
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

    # cleanup title for logging
    title = (re.sub(r'\W+', '', info['title']))[:15]
    title = str((title.encode('ascii',errors='ignore')).decode())

    # check if cached audio exists using modern cache manager
    logger.info("[" + str(request_id) + "] " + "Checking cache for audio...")
    cached_audio_path = cache_manager.get_cached_audio(url, title)
    if cached_audio_path and cached_audio_path.exists():
        try:
            bot.send_audio(chat_id=chat_id, audio=open(cached_audio_path, 'rb'))
            logger.info("[" + str(request_id) + "] " + "Sent cached audio successfully")
        except Exception as e:
            logger.error("[" + str(request_id) + "] " + str(e))
            raise ValueError('Failed to send cached audio.')
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
        logger.error("[" + str(request_id) + "] " + str(e))
        raise ValueError('Failed to apply Vaporwave SFX.')
    except:
        logger.error("[" + str(request_id) + "] " + "Unexpected error:", sys.exc_info()[0])

    # store in cache using modern cache manager
    try:
        cache_key = cache_manager.store_audio(url, outfile, title)
        logger.info("[" + str(request_id) + "] " + f"Stored audio in cache with key: {cache_key}")
    except Exception as e:
        logger.warning("[" + str(request_id) + "] " + f"Failed to cache audio: {e}")

    # send audio to user
    logger.info("[" + str(request_id) + "] " + 'Sending final audio to ' + str(chat_id) + '...')
    try:
        bot.send_audio(chat_id=chat_id, audio=open(vapor_path, 'rb'))
    except Exception as e:
        logger.error("[" + str(request_id) + "] " + str(e))
        raise ValueError('Failed to send audio.')

    # cleanup temporary files (but keep cached version)
    try:
        os.remove(original_path)
        os.remove(chorus_path)
        # Remove the temporary vapor file since it's now cached
        if Path(vapor_path).exists():
            os.remove(vapor_path)
    except OSError as e:
        logger.error("[" + str(request_id) + "] " + str(e))
        pass


# bot handlers
@run_async
def help_command(bot, update):
    """ /help - Shows usage """
    bot.send_message(chat_id=update.message.chat_id, text=help_str)


@run_async
def stats_command(bot, update):
    """ /stats - Shows cache statistics """
    try:
        stats = cache_manager.get_cache_stats()
        stats_text = (
            f"📊 **Cache Statistics**\n\n"
            f"🗃️ **Files**: {stats['total_files']}\n"
            f"💾 **Size**: {stats['total_size_mb']} / {stats['max_size_mb']} MB\n"
            f"🎯 **Hit Rate**: {stats['hit_rate_percent']}%\n"
            f"✅ **Hits**: {stats['hits']}\n"
            f"❌ **Misses**: {stats['misses']}\n"
            f"🔄 **Evictions**: {stats['evictions']}\n"
            f"🧠 **Memory Cache**: {stats['memory_cache_size']} items\n"
            f"🔗 **Redis**: {'✅ Available' if stats['redis_available'] else '❌ Not Available'}"
        )
        bot.send_message(chat_id=update.message.chat_id, text=stats_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        bot.send_message(chat_id=update.message.chat_id, text="❌ Failed to retrieve cache statistics")


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
    global cache_manager
    
    # set env variables
    logger.info("VIRTUAL DREAMS TURNING ON...")
    load_dotenv()
    BOT_TOKEN = os.getenv("TOKEN")
    HEROKU_NAME = "virtualdreamsbot"
    PORT = int(os.environ.get('PORT', '8443'))
    
    # initialize modern cache manager
    redis_url = os.getenv("REDIS_URL")
    cache_dir = os.getenv("CACHE_DIR", "cache")
    max_cache_size_mb = int(os.getenv("CACHE_SIZE_MB", "500"))
    cache_ttl_days = int(os.getenv("CACHE_TTL_DAYS", "7"))
    
    logger.info("Initializing modern cache manager...")
    cache_manager = CacheManager(
        cache_dir=cache_dir,
        redis_url=redis_url,
        max_cache_size_mb=max_cache_size_mb,
        default_ttl=cache_ttl_days * 24 * 3600,
        memory_cache_size=100
    )

    logger.info("Dispatching workers...")
    updater = Updater(token=BOT_TOKEN, workers=2)
    dispatcher = updater.dispatcher

    # define bot handlers
    help_handler = CommandHandler('help', help_command)
    start_handler = CommandHandler('start', help_command)
    vapor_handler = CommandHandler('vapor', vapor_command)
    stats_handler = CommandHandler('stats', stats_command)
    unknown_handler = MessageHandler(Filters.command, unknown_command)

    # start bot handlers
    logger.info("Starting handlers...")
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(vapor_handler)
    dispatcher.add_handler(stats_handler)
    dispatcher.add_handler(unknown_handler)

    # ensure cache directory exists and set working directory
    logger.info("Setting working directory...")
    if not os.path.exists(cache_dir):
        try:
            os.makedirs(cache_dir)
        except OSError as e:
            logger.error(e)
    
    # Set working directory to cache directory for temporary files
    os.chdir(cache_dir)

    # heroku webhook
    updater.start_webhook(listen="0.0.0.0",
                          port=PORT,
                          url_path=BOT_TOKEN)
    updater.bot.setWebhook("https://{}.herokuapp.com/{}".format(HEROKU_NAME, BOT_TOKEN))

    # local hosting
    logger.info("VIRTUAL DREAMS ONLINE")
    # updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
