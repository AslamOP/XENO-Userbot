import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.bot import bot
from core.command import asst_callback, asst_cmd, command, event_handler
from core.plugin_loader import load_plugins
