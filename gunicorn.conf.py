# Servidor de produção da Lyra (gunicorn). Lido automaticamente pelo comando do Procfile.
# UM processo só: o agendador (report, rotinas, lembretes) vive dentro dele — dois processos = dois reports.
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
workers = 1               # nunca aumente: o agendador roda em cada processo
worker_class = "gthread"  # várias conversas ao mesmo tempo dentro do mesmo processo
threads = 16
timeout = 120             # o Slack espera no máximo 3s; o trabalho pesado já roda em segundo plano
graceful_timeout = 30     # no deploy, espera até 30s para terminar o que está em andamento
keepalive = 5
accesslog = "-"           # mantém no log as linhas "POST /slack/events"
loglevel = "info"


def post_worker_init(worker):
    """Depois que o app sobe no processo: liga o agendador (o mesmo que o `python app.py` ligava)."""
    from app import _start_scheduler
    _start_scheduler()
