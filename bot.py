from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from flask import Flask, request, redirect
from waitress import serve
from egybest import *
import telebot
import random
import imdb
import yaml
import os



TOKEN = os.environ['TOKEN']
bot = telebot.TeleBot(token=TOKEN)

server = Flask(__name__)



@bot.message_handler(commands=['start'])
def startCommand(message):
    userID = message.from_user.id
    name = message.from_user.first_name
    
    reply = f'مرحبًا بك يا {name}!'
    try:
        with open('tutorial_msg.txt', 'r', encoding='utf-8') as file:
            tutorial = file.read()
            reply += '\n\n' + tutorial
    finally:
        bot.send_message(userID, reply, parse_mode='Markdown', disable_web_page_preview=True)

    print(f'The User [{userID}] Sent A /start Request')


@bot.message_handler(commands=['help'])
def helpCommand(message):
    userID = message.from_user.id
    
    reply = '⛔ حدث خطأ ⛔'
    try:
        with open('tutorial_msg.txt', 'r', encoding='utf-8') as file:
            tutorial = file.read()
            reply = tutorial
    finally:
        bot.send_message(userID, reply, parse_mode='Markdown', disable_web_page_preview=True)

    print(f'The User [{userID}] Sent A /help Request')


@bot.message_handler(commands=['movie', 'show'], func=lambda msg: len(msg.text.strip().split(' ')) > 1)
def exclusiveSearch(message):
    userID = message.from_user.id
    text = message.text.strip()
    words = text.split(' ')
    query = ' '.join(words[1:])
    command = words[0]
    print(f'The User [{userID}] Sent \"{text}\"')
    searchEgyBest(userID, query, message, includeShows=(command == '/show'), includeMovies=(command == '/movie'))


@bot.message_handler(commands=['rand'])
def randomSelection(message):
    userID = message.from_user.id
    
    isMovie = bool(random.getrandbits(1))
    rand = random.randrange(0, 100)

    imdbInstance = imdb.IMDb()
    if isMovie:
        title = imdbInstance.get_top250_movies()[rand]['title']
    else:
        title = imdbInstance.get_top250_tv()[rand]['title']
    
    print(f'The User [{userID}] Sent A /rand Request and The Bot Chose \"{title}\"')
    searchEgyBest(userID, title, message, includeMovies=isMovie, includeShows=(not isMovie))


@bot.message_handler(func=lambda msg: msg.text is not None and msg.text[0] != '/')
def handleMessages(message):
    userID = message.from_user.id
    text = message.text.strip()
    
    print(f'The User [{userID}] Sent \"{text}\"')

    searchEgyBest(userID, text, message)


@bot.callback_query_handler(func=lambda call: True)
def handleCallback(call):
    links = call.message.caption_entities if len(call.message.caption_entities) > 0 else ''
    requestType = call.data[0]
    index = int(call.data[1:]) if len(call.data) > 1 and call.data[1:].isdigit() else 0
    userID = call.from_user.id
    messageID = call.message.id
    callbackAnswer = None

    
    try:
        yamlData = yaml.safe_load(call.message.caption)
        showLink = links[0].url
        showTitle = yamlData['الاسم']
        show = Show(showLink)
        if requestType == 'S':
            season = show.getSeasons()[index]
            requestEpisodes(userID, messageID=messageID, showLink=showLink, showTitle=showTitle, season=season)
        elif requestType == 'E':
            seasonLink = links[1].url
            seasonNum = yamlData['الموسم']
            season = Season(seasonLink)
            episode = season.getEpisodes()[index]
            requestMediaLinks(userID, messageID=messageID, showLink=showLink, showTitle=showTitle, seasonLink=seasonLink, seasonNum=seasonNum, episode=episode)
        elif requestType == 'B':
            if index == 0:
                show = search(showTitle, includeMovies=False, timeout=10, retries=3)[0]
                requestSeasons(userID, show, messageID)
            
            elif index == 1:
                seasonLink = links[1].url
                seasons = show.getSeasons()

                for i in range(len(seasons)):
                    if seasons[i].link == seasonLink:
                        season = seasons[i]
                        break

                requestEpisodes(userID, messageID=messageID, showLink=showLink, showTitle=showTitle, season=season)
        else:
            bot.delete_message(userID, messageID)
            bot.send_message(userID, '⛔ حدث خطأ ⛔')
    except Exception as e:
        callbackAnswer = '⛔ حدث خطأ ⛔'

    bot.answer_callback_query(call.id, text=callbackAnswer)


def searchEgyBest(userID, query, message, includeMovies=True, includeShows=True):
    try:
        if len(query) < 64:
            results = search(query, includeMovies=includeMovies, includeShows=includeShows, timeout=10, retries=3)
            
            if len(results) > 0:
                result = results[0]
                isShow = isinstance(result, Show)
                    
                if isShow:
                    requestSeasons(userID, result)
                else:
                    requestMediaLinks(userID, episode=result, isMovie=True)

            else:
                print(f'Couldn\'t Find \"{query}\" For [{userID}]')
                bot.reply_to(message, 'لم أستطع العثور على بحثك في إيجي بيست❗')
        else:
            bot.reply_to(message, '⛔ رسالتك طويلة جدًا ⛔')

    except Exception as exception:
        print(f'Exception: {exception}')
        bot.reply_to(message, '⛔ حدث خطأ ⛔')


def requestSeasons(userID, show, messageID=None):
    seasons = show.getSeasons()

    buttons = InlineKeyboardMarkup()
    for i in range(len(seasons)):
        buttons.add(InlineKeyboardButton(seasons[i].title, callback_data=('S' + str(i))))
    
    show.refreshMetadata(posterOnly=True)
    msgCaption = generateMessageCaption(show.link, show.title, rating=show.rating)

    if not messageID:
        try:
            bot.send_photo(userID, show.posterURL, caption=msgCaption, reply_markup=buttons, parse_mode='Markdown')
        except:
            try:
                print(f'Couldn\'t Fetch The Poster of \"{show.title}\"')
                image = open('noimage.jpg', 'rb').read()
                bot.send_photo(userID, image, caption=msgCaption, reply_markup=buttons, parse_mode='Markdown')
            except IOError:
                print(f'Couldn\'t Read \"noimage.jpg\"')
                bot.send_message(userID, '⛔ حدث خطأ ⛔')
    else:
        try:
            bot.edit_message_media(InputMediaPhoto(show.posterURL), chat_id=userID, message_id=messageID)
        finally:
            bot.edit_message_caption(caption=msgCaption, chat_id=userID, message_id=messageID, reply_markup=buttons, parse_mode='Markdown')


def requestEpisodes(userID,  messageID, showLink, showTitle, season):
    episodes = season.getEpisodes()
    
    buttons = InlineKeyboardMarkup()
    for i in range(len(episodes)):
        buttons.add(InlineKeyboardButton(episodes[i].title, callback_data=('E' + str(i))))
    buttons.add(InlineKeyboardButton('العودة ↪', callback_data='B0'))

    season.refreshMetadata(posterOnly=True)

    try:
        bot.edit_message_media(InputMediaPhoto(season.posterURL), chat_id=userID, message_id=messageID)
    finally:
        bot.edit_message_caption(caption=generateMessageCaption(showLink, showTitle, seasonLink=season.link, seasonNum=season.title.split(' ')[-1]), chat_id=userID, message_id=messageID, reply_markup=buttons, parse_mode='Markdown')


def requestMediaLinks(userID, messageID=None, showLink=None, showTitle=None, seasonLink=None, seasonNum=None, episode=None, isMovie=False):
    downloadSources = episode.getDownloadSources()
    
    buttons = InlineKeyboardMarkup()
    for src in downloadSources:
        buttons.add(InlineKeyboardButton(str(src.quality) + 'p', url=src.link))

    if isMovie:
        episode.refreshMetadata(posterOnly=True)
        bot.send_photo(userID, episode.posterURL, caption= generateMessageCaption(episode.link, episode.title, rating=episode.rating), reply_markup=buttons, parse_mode='Markdown')
    else:
        buttons.add(InlineKeyboardButton('العودة ↪', callback_data='B1'))
        bot.edit_message_caption(caption=generateMessageCaption(showLink, showTitle, seasonLink=seasonLink, seasonNum=seasonNum, episodeLink=episode.link, episodeNum=episode.title.split(' ')[1], rating=episode.rating), chat_id=userID, message_id=messageID, reply_markup=buttons, parse_mode='Markdown')


def generateMessageCaption(link, title, seasonLink=None, seasonNum=None, episodeLink=None, episodeNum=None, rating=None):
    caption = f'الاسم: [{title}]({link})'
    
    if seasonNum and seasonLink:
        caption += f'\n\nالموسم: [{seasonNum}]({seasonLink})'
    
    if episodeNum and episodeLink:
        caption += f'\n\nالحلقة: [{episodeNum}]({episodeLink})'

    if rating:
        caption += f'\n\nالتقييم: **{rating}/10** ⭐'

    return caption


@server.route("/" + TOKEN, methods=["POST"])
def getMessageToBot():
	bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
	return "!", 200


@server.route("/", methods=["GET"])
def redirectToTelegram():
	return redirect("https://t.me/EgyBestTeleBot", code=302)



if __name__ == "__main__":
	serve(server, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
