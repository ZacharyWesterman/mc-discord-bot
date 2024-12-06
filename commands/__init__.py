__all__ = ['get', 'all', 'command', 'Command', 'subcommand', 'bad_cmd', 'bad_subcmd', 'Message', 'mc_command', 'db']

from pymongo import MongoClient
from pymongo.database import Database
from typing import Callable
from pathlib import Path
from discord import Message
import subprocess
import asyncio

commands = {}
temp_subcommands = {}

db = MongoClient().flatearth

def command(name: str, description: str, *, admin_only: bool = False) -> Callable:
	def wrapper(object: Command) -> None:
		global temp_subcommands

		obj = object(db)
		obj.subcommands = temp_subcommands
		obj.id = name
		obj.desc = description
		obj.admin_only = admin_only
		temp_subcommands = {}

		commands[name] = obj
		return object

	return wrapper

def subcommand(func: Callable) -> Callable:
	temp_subcommands[func.__name__] = func
	return func

def bad_cmd() -> str:
	return 'ERROR: Unknown command. Type `@mc.skrunky.com`, `!help` or `/help` for a list of commands.'

def bad_subcmd(subcmd: str) -> str:
	f'ERROR: Invalid subcommand "{subcmd}".'

def mc_command(text: str) -> None:
	subprocess.run(['screen', '-r', 'flatearth', '-p', '0', '-X', 'stuff', text.replace('\\','\\\\').replace('$', '\\$') + '\\n'])

class Command:
	def __init__(self, db: Database) -> None:
		self.db: Database = db
		self.subcommands: dict[str, Callable] = {}
		self.id: str = 'NO ID'
		self.desc: str = 'NO DESCRIPTION'
		self.admin_only: bool = False
		self.user_is_admin: bool = False
		self.sub = 'NO SUB'

	def __str__(self) -> str:
		return f'!{self.id}'

	def log(self, msg: str) -> None:
		print(msg, flush=True)

	def default(self, message: Message, command: list[str]) -> str:
		return bad_subcmd(command[0])

	async def call(self, message: Message, command: list[str]) -> str:
		self.user_is_admin = bool(self.db.admins.find_one({'id': str(message.author.id)}))

		if not self.user_is_admin and self.admin_only:
			return bad_cmd()

		if len(command) and command[0] in self.subcommands:
			params = {'self': self, 'message': message, 'command': command[1::]}
			method = self.subcommands[command[0]]
			self.sub = command[0]
		else:
			params = {'message': message, 'command': command}
			method = self.default
			self.sub = 'NO SUB'

		if asyncio.iscoroutinefunction(method):
			return await method(**params)
		else:
			return method(**params)

def get(name: str) -> Command|None:
	return commands.get(name)

def all() -> dict[str, Command]:
	return commands

#Dynamically import and register all commands in the 'commands' directory.
for i in [f.name[:-3] for f in Path(__file__).parent.iterdir() if f.name != '__init__.py' and not f.is_dir()]:
	__import__(f'commands.{i}')
