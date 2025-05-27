"""
Command to view and edit points of interest in the Flat Earth.
"""

import re
from datetime import datetime
from math import ceil

from discord import Message

from commands import Command, bad_subcmd, command, subcommand

MAX_POI = 10


@command('location', 'View or edit points of interest in the Flat Earth.', 'minecraft')
class LocationCmd(Command):
    """
    Command to view and edit points of interest in the Flat Earth.
    """

    def count_valid_messages(self) -> int:
        """
        Count the number of valid messages that have been marked with emojis.

        Returns:
            int: The count of valid messages with emojis.
        """
        return self.db.messages.count_documents({
            'emojis.0': {'$exists': True},
        })

    def get_valid_messages(self, start: int, count: int) -> list[dict]:
        """
        Get a list of valid messages that have been marked with emojis.

        Args:
            start (int): The starting index for pagination.
            count (int): The number of messages to retrieve.

        Returns:
            list[dict]: A list of messages that have emojis.
        """

        return [
            i for i in self.db.messages.find({
                'emojis.0': {'$exists': True},
            }).sort({'label': 1}).skip(start).limit(count)
        ]

    def count_messages(self, label: str) -> int:
        """
        Count the number of messages with a specific label.

        Args:
            label (str): The label to search for in the messages.

        Returns:
            int: The count of messages with the specified label.
        """
        return self.db.messages.count_documents({'label': label.upper()})

    def find_message(self, label: str) -> dict | None:
        """
        Find a message by its label.

        Args:
            label (str): The label to search for in the messages.

        Returns:
            dict | None: The message document if found, otherwise None.
        """
        return self.db.messages.find_one({'label': label.upper()})

    def get_emojis(self, message: Message) -> dict[str, str]:
        """
        Get the emojis for the different dimensions based on the discord server's custom emojis.

        Args:
            message (Message): The Discord message object to check for custom emojis.

        Returns:
            dict[str, str]: A dictionary mapping dimension names to their corresponding emojis.
        """

        emojis = {
            'overworld': 'overworld ',
            'nether': 'nether ',
            'end': 'end ',
        }
        if message.guild:
            for i in ['overworld', 'nether', 'end']:
                for emoji in message.guild.emojis:
                    if emoji.name == i:
                        emojis[i] = f'<:{i}:{emoji.id}>'

        return emojis

    def update_message_emojis(self, id: int, emojis: list[str]) -> None:
        """
        Update the emojis for a message with the given ID.

        Args:
            id (int): The ID of the message to update.
            emojis (list[str]): A list of emojis to set for the message.
        """
        self.db.messages.update_one({'message_id': id}, {'$set': {
            'emojis': emojis,
            'updated': True,
            'last_updated': datetime.utcnow(),
        }})

    async def default(self, message: Message, cmd: list[str]) -> str:
        if not len(cmd) > 0 or cmd[0] == 'help':
            return '\n'.join([
                'View or edit points of interest in the Flat Earth.',
                'Note that points of interest are sorted alphabetically.',
                f'* `{self} list`: Show the first page of all points of interest.',
                f'* `{self} list {{page}}`: Show the given page of points of interest.',
                f'* `{self} count`: Show the total number of points of interest.',
                (
                    f'* `{self} delete {{location name}}`: Delete a point of interest. ' +
                    'The name is not case sensitive.'
                ),
                (
                    'To add a new point of interest, ' +
                    'type a description of the location along with the coordinates, ' +
                    'then click an emoji indicating what dimension it\'s in.'
                ),
                (
                    'For example, `village -123 456`, `-12,34,-56 mesa biome`, ' +
                    'and `deep 123,-456 dark` are all valid points of interest.'
                ),
                (
                    'To rename a point of interest, just add a ' +
                    'new one with the exact same coordinates.'
                ),
                (
                    'To delete a point of interest, remove all your emojis from the ' +
                    f'original message, or use the `{self} delete` command.'
                ),
            ])

        return bad_subcmd(cmd[0])

    @subcommand
    async def count(self, message: Message, cmd: list[str]) -> str:
        """
        Count the number of points of interest.

        Args:
            message (Message): The Discord message object.
            cmd (list[str]): The command arguments, where the first argument is 'count'.

        Returns:
            str: A message indicating the total number of
                points ofinterest and the number of pages.
        """
        msg_ct = self.count_valid_messages()
        page_ct = ceil(msg_ct / MAX_POI)
        return (
            f'There are {msg_ct} points of interest ' +
            f'({page_ct} page{"s" if page_ct != 1 else ""}).'
        )

    @subcommand
    async def delete(self, message: Message, cmd: list[str]) -> str:
        """
        Delete a point of interest by its label.

        Args:
            message (Message): The Discord message object.
            cmd (list[str]): The command arguments, where the first argument
                is the label of the point of interest to delete.

        Returns:
            str: A message indicating the result of the deletion operation.
        """

        if len(cmd) == 0:
            return 'ERROR: Please specify a point of interest to delete.'

        label = ' '.join(cmd)
        ct = self.count_messages(label)

        if ct == 0:
            return f'No point of interest was found with label `{label}`.'

        if ct > 1:
            return (
                'Multiple points of interest were found with that label... ' +
                'Please talk to zachy this shouldn\'t be happening :('
            )

        msg = self.find_message(label)
        if msg is None:
            return 'ERROR: PoI exists but also doesnt??? Poke and prod zachy!!'

        self.update_message_emojis(
            msg['message_id'], [])  # Delete all locations
        return f'Deleted `{msg["label"]}`.'

    @subcommand
    async def list(self, message: Message, cmd: list[str]) -> str:
        """
        List all points of interest, paginated.

        Args:
            message (Message): The Discord message object.
            cmd (list[str]): The command arguments, where the first argument
                is the page number to display.

        Returns:
            str: A message listing the points of interest for the specified page.
        """

        response = ''
        page_number = 1
        msg_ct = self.count_valid_messages()
        page_ct = ceil(msg_ct / MAX_POI)

        if len(cmd):
            if not re.match(r'^\d+$', cmd[0]) or int(cmd[0]) < 1:
                response += f'Invalid page number `{cmd[0]}`, defaulting to `1`.\n'
                page_number = 1
            else:
                page_number = int(cmd[0])

        if page_number > page_ct:
            response += f'Invalid page number `{page_number}`, defaulting to `{page_ct}`.\n'
            page_number = page_ct

        emojis = self.get_emojis(message)

        response += f'Points of interest, page {page_number} of {page_ct} ({msg_ct} total)'
        for i in self.get_valid_messages((page_number - 1) * MAX_POI, MAX_POI):
            response += (
                f"\n> `{i.get('label', 'ERR: NO LABEL')}`: " +
                f"{i.get('coords', [])} " +
                f"{''.join(emojis[i] for i in i.get('emojis', []))}"
            )

        return response
