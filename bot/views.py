import json
import logging

from django.http import (
    HttpResponse,
    JsonResponse,
)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_exempt

from bot.processors.greeting import GreetingBotModule
from bot.processors.pennychat import PennyChatBotModule
from bot.processors.base import Bot
from common.utils import get_slack_client

slack_client = get_slack_client()
bot = Bot(event_processors=[GreetingBotModule(slack_client), PennyChatBotModule(slack_client)])


def index(request):
    return HttpResponse("At least something works!!!!")


@xframe_options_exempt
@csrf_exempt
def hook(request):
    blob = json.loads(request.body)
    logging.info(f'HOOK> {request.body.decode("utf-8")}')

    if 'challenge' in blob:
        return HttpResponse(json.loads(request.body)['challenge'])

    event = blob['event']
    is_bot = False
    if 'subtype' in event and event['subtype'] == 'bot_message':
        is_bot = True
    if not is_bot:
        bot(event)

    logging.info('HOOK SLACK>')
    slack_client.mock_log_all_calls()  # TODO!
    return HttpResponse('')


@xframe_options_exempt
@csrf_exempt
def interactive(request):
    event = json.loads(request.POST['payload'])
    logging.info(f'INTERACTIVE> {request.POST["payload"]}')
    resp = bot(event)
    if resp:
        return JsonResponse(resp)

    logging.info('INTERACTIVE SLACK>')
    slack_client.mock_log_all_calls()  # TODO!
    return HttpResponse()


@csrf_exempt
def command(request):
    event = request.POST
    logging.info(f'COMMAND> {request.POST}')
    command = event['text'].split(' ', 1)[0]
    if command == 'chat':
        PennyChatBotModule.create_penny_chat(slack_client, event)
    elif command == 'help':
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "I can help you make a new Penny Chat! Type `/penny chat` to get started.\n"
                            "_More features coming soon..._"
                }
            }
        ]
        slack_client.chat_postEphemeral(channel=event['channel_id'], user=event['user_id'], blocks=blocks)

    logging.info('COMMAND SLACK>')
    slack_client.mock_log_all_calls()  # TODO!
    return HttpResponse('')
