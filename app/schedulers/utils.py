from .starter import scheduler

import logging

def pause_job(job_id: str):
    try:
        scheduler.pause_job(job_id, jobstore='default')
        job = scheduler.get_job(job_id, jobstore='default')
        logging.info(f"Job paused: {job}")
    except Exception as e:
        logging.error(e)
        
def resume_job(job_id: str):
    try:
        scheduler.resume_job(job_id, jobstore='default')
        job = scheduler.get_job(job_id, jobstore='default')
        logging.info(f"Job resumed: {job}")
    except Exception as e:
        logging.error(e)