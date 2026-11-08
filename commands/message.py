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
        # Convert color tags to minecraft colors.
        '&black;': '§0',
        '&dark_blue;': '§1',
        '&darkblue;': '§1',
        '&blue;': '§1',
        '&dark_green;': '§2',
        '&darkgreen;': '§2',
        '&green;': '§2',
        '&dark_aqua;': '§3',
        '&dark_cyan;': '§3',
        '&darkaqua;': '§3',
        '&darkcyan;': '§3',
        '&aqua;': '§3',
        '&teal;': '§3',
        '&dark_red;': '§4',
        '&darkred;': '§4',
        '&red;': '§4',
        '&dark_purple;': '§5',
        '&darkpurple;': '§5',
        '&purple;': '§5',
        '&gold;': '§6',
        '&orange;': '§6',
        '&gray;': '§7',
        '&grey;': '§7',
        '&light_gray;': '§7',
        '&light_grey;': '§7',
        '&lightgray;': '§7',
        '&lightgrey;': '§7',
        '&dark_gray;': '§8',
        '&dark_grey;': '§8',
        '&darkgray;': '§8',
        '&darkgrey;': '§8',
        '&light_blue;': '§9',
        '&lightblue;': '§9',
        '&light_green;': '§a',
        '&lightgreen;': '§a',
        '&lime;': '§a',
        '&light_aqua;': '§b',
        '&lightaqua;': '§b',
        '&cyan;': '§b',
        '&light_red;': '§c',
        '&lightred;': '§c',
        '&pink;': '§c',
        '&light_purple;': '§d',
        '&lightpurple;': '§d',
        '&magenta;': '§d',
        '&yellow;': '§e',
        '&white;': '§f',
        '&minecoin_gold;': '§g',
        '&light_gold;': '§g',
        '&u;': '§u',
        '&underline;': '§u',
        '&underlined;': '§u',
        '&b;': '§l',
        '&bold;': '§l',
        '&i;': '§o',
        '&italic;': '§o',
        '&italics;': '§o',
        '&s;': '§m',
        '&strike;': '§m',
        '&strikethrough;': '§m',
        '&o;': '§k',
        '&obfuscate;': '§k',
        '&obfuscated;': '§k',
        '&random;': '§k',
        '&hide;': '§k',
        '&hidden;': '§k',
        '&r;': '§r',
        '&reset;': '§r',

        # Replace special characters so text formatting doesn't get weird...
        '“': '"',
        '”': '"',
        '‘': "'",
        '’': "'",
        '…': "...",

        # Replace common sigils so text formatting doesn't get weird...
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

        send_message_minecraft(alias, ' '.join(cmd))

        return None, '✅'  # Don't respond to the message, just react to it.
