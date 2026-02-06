from apscheduler.schedulers.asyncio import AsyncIOScheduler


scheduler = AsyncIOScheduler()

def start_scheduler(bot, check_signals):
    scheduler.add_job(
        check_signals,
        'cron',
        name="check_5m",
        minute='*/5',
        second=1,
        kwargs={'bot': bot, 'interval': '5m'},
        id='check_5m'
    )

    scheduler.add_job(
        check_signals,
        'cron',
        name="check_15m",
        minute='*/15',
        second=15,
        kwargs={'bot': bot, 'interval': '15m'},
        id='check_15m'
    )

    scheduler.add_job(
        check_signals,
        'cron',
        name="check_30m",
        minute='*/30',
        second=30,
        kwargs={'bot': bot, 'interval': '30m'},
        id='check_30m'
    )

    scheduler.add_job(
        check_signals,
        'cron',
        name="check_1h",
        hour='*/1',
        minute=0,
        second=45,
        kwargs={'bot': bot, 'interval': '1h'},
        id='check_1h'
    )

    scheduler.add_job(
        check_signals,
        'cron',
        name="check_4h",
        hour='*/4',
        minute=1,
        second=0,
        kwargs={'bot': bot, 'interval': '4h'},
        id='check_4h'
    )


    scheduler.start()