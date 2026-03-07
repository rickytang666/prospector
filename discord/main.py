import logging
import json
import os
import platform
import random
import sys

import discord

from discord.ext import commands, tasks
from discord.ext.commands import Context
from dotenv import load_dotenv

load_dotenv();