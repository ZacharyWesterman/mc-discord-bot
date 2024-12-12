from commands import *
import json

# Fake a player message


def send_message_minecraft(author: str, content: str) -> None:
    repl = {
        '“': '"',
        '”': '"',
        '‘': "'",
        '’': "'",
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
    for i in repl:
        content = content.replace(i, repl[i])

    response = {
        'rawtext': [{
            'text': f'<{author}> {content}'
        }]
    }
    mc_command('tellraw @a ' + json.dumps(response))


@command('say', 'Send a message to the Flat Earth.', 'minecraft')
class MessageCmd(Command):
    def get_alias(self, user_id: str) -> str | None:
        if data := self.db.users.find_one({'user_id': user_id}):
            return data.get('alias')
        return None

    def default(self, message: Message, command: list[str]) -> str:
        if not len(command) or command[0] == 'help':
            return '\n'.join([
                'To send a message to the Flat Earth, specify some text like `!say your message here`.',
                'Alternatively, you can DM me and all messages will go directly to the Flat Earth.',
            ])

        alias = self.get_alias(message.author.id)
        if alias := self.get_alias(message.author.id):
            self.log(f'Received DM from {
                     message.author}({alias}): {message.content}')
        else:
            alias = str(message.author)
            self.log(f'Received DM from {message.author}: {message.content}')

        send_message_minecraft(alias, ' '.join(command[1::]))

        return None, '✅'  # Don't respond to the message, just react to it.
