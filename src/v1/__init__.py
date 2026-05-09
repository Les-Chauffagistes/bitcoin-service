from .app import app as subapp, routes
from init import app, log
from . import handlers

subapp.add_routes(routes)
app.add_subapp("/v1", subapp)
log.debug("routes added")