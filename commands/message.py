"""A command to send a message to the Flat Earth."""

import json
from typing import Any

from discord import Message

from commands import Command, command, mc_command


def send_message_minecraft(author: str, content: str) -> None:
    """
    Send a message to the Minecraft server as if it was sent by a player.

    Args:
        author (str): The name of the player sending the message.
        content (str): The content of the message to be sent.
    """

    # Don't send empty messages
    if not content:
        return

    repl = {
        '“': '"',
        '”': '"',
        '‘': "'",
        '’': "'",
        '…': "...",
        '😀': ':)',
        '😃': ':D',
        '😄': '=)',
        '😆': 'XD',
        '😉': ';)',
        '😅': '^_^\'',
        '🤗': ':hug',
        '😁': ':D',
        '😂': 'XD',
        '😊': '^_^',
        '😍': '<3',
        '😘': ':-*',
        '😜': ';P',
        '😎': 'B)',
        '😔': ':(',
        '😢': ':\'(',
        '😡': '>:(',
        '😱': ':O',
        '😴': '-_-',
        '👍': ':thumbsup:',
        '👏': ':clap:',
        '🙌': '\\o/',
        '🙏': ':pray:',
        '💪': ':muscle:',
        '🎉': ':party:',
        '🌟': ':star:',
    }
    for key, val in repl.items():
        content = content.replace(key, val)

    response = {
        'rawtext': [{
            'text': f'<{author}> {content}'
        }]
    }
    mc_command('tellraw @a ' + json.dumps(response))


@command('say', 'Send a message to the Flat Earth.', 'minecraft')
class MessageCmd(Command):
    """
    Command to send a message to the Flat Earth Minecraft server.
    This command allows users to send messages that will appear in the Minecraft chat,
    formatted as if they were sent by a player with an alias.
    """

    def get_alias(self, user_id: int) -> str | None:
        """
        Get the alias for a user.

        Args:
            user_id (int): The ID of the user whose alias is to be retrieved.

        Returns:
            str | None: The alias of the user if it exists, otherwise None.
        """

        if data := self.db.users.find_one({'user_id': user_id}):
            return data.get('alias')
        return None

    async def default(self, message: Message, cmd: list[str]) -> Any:
        if len(cmd) == 0 or cmd[0] == 'help':
            return ''.join([
                'To send a message to the Flat Earth, ',
                'specify some text like `!say your message here`.\n',
                'Alternatively, you can DM me and all messages ',
                'will go directly to the Flat Earth.',
            ]), None

        alias = self.get_alias(message.author.id)
        if alias := self.get_alias(message.author.id):
            self.log(f'Received DM from {message.author}({alias}): {message.content}')
        else:
            alias = str(message.author)
            self.log(f'Received DM from {message.author}: {message.content}')

        send_message_minecraft(alias, ' '.join(cmd[1::]))

        return None, '✅'  # Don't respond to the message, just react to it.
