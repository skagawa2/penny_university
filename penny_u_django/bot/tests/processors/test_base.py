from bot.processors.base import (
    Bot,
    Event,
    BotModule,
    event_filter,
    event_filter_factory,
)


def test_Bot(mocker):
    processor = mocker.Mock()
    bot = Bot(event_processors=[processor])
    bot(Event({'some':'message'}))
    assert processor.call_args == mocker.call({'some': 'message'})


def test_BotModule(mocker):
    tester = mocker.Mock()
    class MyBotModule(BotModule):
        def something(self, event):
            tester(event)

    my_bot_module = MyBotModule()
    my_bot_module(Event({'some': 'message'}))

    assert tester.call_args == mocker.call({'some': 'message'})


def test_event_filter(mocker):
    tester = mocker.Mock()

    @event_filter(lambda e: e['call_me'])
    def my_func(event):
        tester(event)

    assert my_func.__name__ == 'my_func'  # otherwise we're not transferring the function properties correctly

    my_func(Event({'call_me': False}))
    assert tester.called is False

    my_func(Event({'call_me': True}))
    assert tester.call_args == mocker.call({'call_me': True})


def test_event_filter_factory(mocker):
    tester = mocker.Mock()

    @event_filter_factory
    def is_color(color):
        def filter_func(event):
            return event['color'] == color
        return filter_func

    assert is_color.__name__ == 'is_color'  # otherwise we're not transferring the function properties correctly

    @is_color('green')
    def my_func(event):
        tester(event)

    assert my_func.__name__ == 'my_func'

    my_func(Event({'color': 'red'}))
    assert tester.called is False

    my_func(Event({'color': 'green'}))
    assert tester.call_args == mocker.call({'color': 'green'})
