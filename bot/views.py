import json
import logging
from pprint import pprint

from django.conf import settings
import slack

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_exempt

from bot.processors.greeting import GreetingBotModule
from bot.processors.pennychat import PennyChatBotModule
from bot.processors.base import (
    Bot,
    Event,
)

slack_client = slack.WebClient(token=settings.SLACK_API_KEY)
bot = Bot(event_processors=[GreetingBotModule(slack_client), PennyChatBotModule(slack_client)])


def index(request):
    return HttpResponse("At least something works!!!!")


@xframe_options_exempt
@csrf_exempt
def hook(request):
    blob = json.loads(request.body)
    message_logger = logging.getLogger('messages')
    message_logger.info(request.body)

    if 'challenge' in blob:
        return HttpResponse(json.loads(request.body)['challenge'])
    else:
        print(blob)
        event = blob['event']
        is_bot = False
        if 'subtype' in event and event['subtype'] == 'bot_message':
            is_bot = True
        if not is_bot:
            bot(Event(event))
        return HttpResponse('')


@xframe_options_exempt
@csrf_exempt
def interactive(request):
    payload = json.loads(request.POST['payload'])
    message_logger = logging.getLogger('messages')
    message_logger.info(request.POST['payload'])

    bot(Event(payload))

    return HttpResponse('')


@csrf_exempt
def penny_chat(request):
    event = request.POST
    PennyChatBotModule.create_penny_chat(slack_client, event)
    return HttpResponse('')


@csrf_exempt
def command(request):
    event = request.POST
    command_and_args = event['text'].split(' ', 1)

    command = command_and_args[0]
    arguments = ''
    if len(command_and_args) > 1:
        arguments = command_and_args[1]

    if command == 'chat':
        PennyChatBotModule.create_penny_chat(slack_client, event)
    elif command == 'help':
        print('no! I wont help you with ', arguments)
    elif command == 'search':
        print('search serch ', arguments)

    return HttpResponse('')

