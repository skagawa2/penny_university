import json
import urllib.parse
from datetime import timedelta

from background_task import background
from django.conf import settings
from pytz import utc
from slack import WebClient

from pennychat.models import (
    PennyChatInvitation,
    Participant,
)
from users.models import (
    get_or_create_user_profile_from_slack_ids,
    UserProfile,
)

VIEW_SUBMISSION = 'view_submission'
VIEW_CLOSED = 'view_closed'

PENNY_CHAT_DATE = 'penny_chat_date'
PENNY_CHAT_TIME = 'penny_chat_time'
PENNY_CHAT_USER_SELECT = 'penny_chat_user_select'
PENNY_CHAT_CHANNEL_SELECT = 'penny_chat_channel_select'
PENNY_CHAT_DETAILS = 'penny_chat_details'
PENNY_CHAT_EDIT = 'penny_chat_edit'
PENNY_CHAT_SHARE = 'penny_chat_share'
PENNY_CHAT_CAN_ATTEND = 'penny_chat_can_attend'
PENNY_CHAT_CAN_NOT_ATTEND = 'penny_chat_can_not_attend'

PENNY_CHAT_ID = 'penny_chat_id'


def _get_slack_client():
    # TODO memoize the slack_client, but remember that it has to be thread safe, so figure out some way to memoize
    # per-thread
    # TODO move to common/utils.py
    return WebClient(settings.SLACK_API_KEY)


@background
def post_organizer_edit_after_share_template(penny_chat_view_id):
    # TODO! replace penny_chat_view_id with penny_chat_invitation_id
    slack_client = _get_slack_client()

    penny_chat_invitation = PennyChatInvitation.objects.get(view=penny_chat_view_id)
    slack_client.chat_postMessage(
        channel=penny_chat_invitation.organizer_slack_id,
        blocks=organizer_edit_after_share_template(slack_client, penny_chat_invitation),
    )


@background
def share_penny_chat_invitation(penny_chat_id):
    penny_chat_invitation = PennyChatInvitation.objects.get(id=penny_chat_id)
    organizer = UserProfile.objects.get(  # TODO! turn this into penny_chat.organizer @property
        user_chats__penny_chat=penny_chat_invitation,
        user_chats__role=Participant.ORGANIZER,
    )
    slack_client = _get_slack_client()

    # unshare the old shares
    old_shares = json.loads(penny_chat_invitation.shares or '{}')
    for channel, ts in old_shares.items():
        if channel[0] != 'C':
            # skip users etc. because yu can't chat_delete messages posted to private channels
            # TODO investigate something better to do here
            # https://github.com/penny-university/penny_university/issues/140 might resolve this
            continue
        try:
            slack_client.chat_delete(channel=channel, ts=ts)
        except:  # noqa
            # can't do anything about it anyway... might as well continue
            pass
    invitation_blocks = shared_message_template(penny_chat_invitation, organizer.real_name, include_rsvp=True)
    shares = {}
    for share_to in comma_split(penny_chat_invitation.channels) + comma_split(penny_chat_invitation.invitees):
        resp = slack_client.chat_postMessage(
            channel=share_to,
            blocks=invitation_blocks,
        )
        shares[resp.data['channel']] = resp.data['ts']
    penny_chat_invitation.shares = json.dumps(shares)
    penny_chat_invitation.save()


def datetime_template(penny_chat):
    timestamp = int(penny_chat.date.astimezone(utc).timestamp())
    date_text = f'<!date^{timestamp}^{{date_pretty}} at {{time}}|{penny_chat.date}>'
    return date_text


def shared_message_template(penny_chat, user_name, include_rsvp=False):
    start_date = penny_chat.date.astimezone(utc).strftime('%Y%m%dT%H%M%SZ')
    end_date = (penny_chat.date.astimezone(utc) + timedelta(hours=1)).strftime('%Y%m%dT%H%M%SZ')
    google_cal_url = 'https://calendar.google.com/calendar/render?' \
                     'action=TEMPLATE&text=' \
        f'{urllib.parse.quote(penny_chat.title)}&dates=' \
        f'{start_date}/{end_date}&details=' \
        f'{urllib.parse.quote(penny_chat.description)}'

    body = [
        {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': f'_*{user_name}* invited you to a new Penny Chat!_'
            }
        },
        {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': f'*Title*\n{penny_chat.title}'
            }
        },
        {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': f'*Description*\n{penny_chat.description}'
            }
        },
        {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': f'*Date and Time*\n{datetime_template(penny_chat)}'
            },
            'accessory': {
                'type': 'button',
                'text': {
                    'type': 'plain_text',
                    'text': 'Add to Google Calendar :calendar:',
                    'emoji': True
                },
                'url': google_cal_url
            }
        },
    ]

    if include_rsvp:
        body.append(
            {
                'type': 'actions',
                'elements': [
                    {
                        'type': 'button',
                        'text': {
                            'type': 'plain_text',
                            'text': 'Count me in :thumbsup:',
                            'emoji': True,
                        },
                        'action_id': PENNY_CHAT_CAN_ATTEND,
                        'value': json.dumps({PENNY_CHAT_ID: penny_chat.id}),  # TODO should this be a helper function?
                        'style': 'primary',
                    },
                    {
                        'type': 'button',
                        'text': {
                            'type': 'plain_text',
                            'text': 'I can\'t make it :thumbsdown:',
                            'emoji': True,
                        },
                        'action_id': PENNY_CHAT_CAN_NOT_ATTEND,
                        'value': json.dumps({PENNY_CHAT_ID: penny_chat.id}),
                        'style': 'primary',
                    }

                ]
            }
        )

    return body


def organizer_edit_after_share_template(slack_client, penny_chat_invitation):
    shares = []
    users = get_or_create_user_profile_from_slack_ids(
        comma_split(penny_chat_invitation.invitees),
        slack_client=slack_client,
    )
    for slack_user_id in comma_split(penny_chat_invitation.invitees):
        shares.append(users[slack_user_id].real_name)

    organizer = get_or_create_user_profile_from_slack_ids(
        [penny_chat_invitation.organizer_slack_id],
        slack_client=slack_client,
    ).get(penny_chat_invitation.organizer_slack_id)

    if len(penny_chat_invitation.channels) > 0:
        for channel in comma_split(penny_chat_invitation.channels):
            shares.append(f'<#{channel}>')

    if len(shares) == 1:
        share_string = shares[0]
    elif len(shares) == 2:
        share_string = ' and '.join(shares)
    elif len(shares) > 2:
        shares[-1] = f'and {shares[-1]}'
        share_string = ', '.join(shares)

    shared_message_preview_blocks = shared_message_template(penny_chat_invitation, organizer.real_name) + [
        {
            'type': 'divider'
        },
        {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': f'*:point_up: You just shared this invitation with:* {share_string}. '
                    'We will notify you as invitees respond.\n\n'
                    'In the meantime if you need to update the event, click the button below.'
            }
        },
        {
            'type': 'actions',
            'elements': [
                {
                    'type': 'button',
                    'text': {
                        'type': 'plain_text',
                        'text': 'Edit Details :pencil2:',
                        'emoji': True,
                    },
                    # TODO should this be a helper function?
                    'value': json.dumps({PENNY_CHAT_ID: penny_chat_invitation.id}),
                    'action_id': PENNY_CHAT_EDIT,
                    'style': 'primary',
                }

            ]
        },
    ]

    return shared_message_preview_blocks


def comma_split(comma_delimited_string):
    """normal string split for  ''.split(',') returns [''], so using this instead"""
    return [x for x in comma_delimited_string.split(',') if x]
