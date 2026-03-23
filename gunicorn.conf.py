# ============================================================
# Gunicorn production configuration for Halal Check API
# ============================================================
# Uses Uvicorn workers for ASGI support with FastAPI

import os

# Server socket
bind = f"{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '8000')}"

# Worker processes
workers = int(os.getenv('WORKERS', '4'))
worker_class = 'uvicorn.workers.UvicornWorker'

# Worker tuning
worker_connections = int(os.getenv('WORKER_CONNECTIONS', '1000'))
timeout = int(os.getenv('TIMEOUT', '120'))
keepalive = int(os.getenv('KEEPALIVE', '5'))
graceful_timeout = int(os.getenv('GRACEFUL_TIMEOUT', '30'))
max_requests = int(os.getenv('MAX_REQUESTS', '5000'))
max_requests_jitter = int(os.getenv('MAX_REQUESTS_JITTER', '500'))

# Preload application (shares memory across workers)
preload_app = True

# Logging
accesslog = '-'  # stdout
errorlog = '-'   # stderr
loglevel = os.getenv('LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Security
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190


def on_starting(server):
    """Called before the master process is initialized."""
    pass


def post_fork(server, worker):
    """Called after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)


def pre_exec(server):
    """Called before a new master process is forked (e.g. during reload)."""
    server.log.info("Forked child, re-executing.")


def when_ready(server):
    """Called when the server is ready to accept connections."""
    server.log.info("Server is ready. Spawned workers: %d", server.num_workers)


def worker_int(worker):
    """Called when a worker receives the INT signal."""
    worker.log.info("Worker received INT signal")


def worker_abort(worker):
    """Called when a worker times out."""
    worker.log.info("Worker (pid: %s) aborted", worker.pid)
