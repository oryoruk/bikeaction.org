release: python manage.py migrate
web: gunicorn -c gunicorn.conf.py pbaabp.asgi --bind :$PORT
worker: python -m celery -A pbaabp worker -c 1 --beat -l INFO
discordworker: python manage.py run_discord
