from celery import Celery
import os

def make_celery(app):
    redis_url = os.getenv('redis://red-cvl1ohre5dus73bv2ha0:6379', 'redis://localhost:6379/0')  # Fallback para local
    celery = Celery(
        app.import_name,
        backend=redis_url,
        broker=redis_url
    )
    celery.conf.update(app.config)
    return celery

def init_celery(app):
    celery = make_celery(app)
    return celery



