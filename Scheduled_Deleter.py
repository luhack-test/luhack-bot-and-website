# Created by DethMetalDuck
# Scheduled_Deleter is a small script that, when run, deletes tokens from the database that have expired. This is currently set to delete every 1 minute, and tokens expire after 30 minutes
import sched
import time
import Token_Handler
import datetime

scheduler = sched.scheduler(time.time, time.sleep)


def scheduled_deletion(sc):
    print("Deleting tokens - " + str(datetime.datetime.now()))
    Token_Handler.delete_expired_tokens()
    scheduler.enter(60, 1, scheduled_deletion, (sc,))


scheduler.enter(60, 1, scheduled_deletion, (scheduler,))
scheduler.run()
