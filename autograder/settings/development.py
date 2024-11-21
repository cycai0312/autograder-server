import os

from .base import *

MEDIA_ROOT += '_dev'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# When true, the function autograder.rest_api.serve_file.serve_file
# will return a response that uses nginx's X-accel capability
# https://www.nginx.com/resources/wiki/start/topics/examples/x-accel/
# Can be overridden by settings the environment variable with the same
# name to "false" to disable or "true" to enable.
USE_NGINX_X_ACCEL = os.environ.get('USE_NGINX_X_ACCEL', 'false') == 'true'

INSTALLED_APPS += [
    # Used for testing ag_model_base
    'autograder.core.tests.test_models',
]

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

INSTALLED_APPS += [
    'debug_toolbar',
]
def show_toolbar_callback(request):
    return DEBUG
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': show_toolbar_callback
}
DEBUG_TOOLBAR_PANELS = [
    'debug_toolbar.panels.versions.VersionsPanel',
    'debug_toolbar.panels.timer.TimerPanel',
    'debug_toolbar.panels.settings.SettingsPanel',
    'debug_toolbar.panels.headers.HeadersPanel',
    'debug_toolbar.panels.request.RequestPanel',
    'debug_toolbar.panels.sql.SQLPanel',
    'debug_toolbar.panels.profiling.ProfilingPanel',
    # 'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    # 'debug_toolbar.panels.templates.TemplatesPanel',
    'debug_toolbar.panels.cache.CachePanel',
    'debug_toolbar.panels.signals.SignalsPanel',
    'debug_toolbar.panels.logging.LoggingPanel',
    'debug_toolbar.panels.redirects.RedirectsPanel',
]
MIDDLEWARE += (
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'autograder.non_html_debug_toolbar_middleware.NonHtmlDebugToolbarMiddleware',
)

REST_FRAMEWORK.update({
    'TEST_REQUEST_DEFAULT_FORMAT': 'json'
})

if os.environ.get('USE_REAL_AUTH', 'true').lower() == 'false':
    REST_FRAMEWORK.update({
        'DEFAULT_AUTHENTICATION_CLASSES': (
            'autograder.rest_api.auth.DevAuth',
        )
    })

# ----- Celery settings ----- #

# For testing without celery server running
TEST_RUNNER = 'autograder.grading_tasks.celery_test_runner.CeleryTestSuiteRunner'

AG_TEST_MAX_RETRIES = 2
AG_TEST_MIN_RETRY_DELAY = 1
AG_TEST_MAX_RETRY_DELAY = 2
