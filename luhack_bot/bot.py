# Created by DethMetalDuck
# LUHack_Discord_Verification_Bot contains the main logic for the bot
import time

import discord
from discord.ext.commands import Bot

from luhack_bot import database_handler, email_handler, token_handler
from luhack_bot.secrets import bot_client_token

***REMOVED***
***REMOVED***
***REMOVED***

# Secret client token :^)
TOKEN = bot_client_token

# Initialise discord client
client = Bot(command_prefix="L!", pm_help=True)

# Remove default help command so we can write our own
client.remove_command("help")


# Help command
@client.command(
    name="Help",
    description="Provides a list of available commands",
    brief="For when you have no idea what's going on",
    aliases=["help", "info", "Info", "nani_the_fuck"],
)
async def help(context):
    description = "An autonomous entity, forged in the magical fires of the IoT Space Bulb. Interact with this wonderous construct using: "
    embed = discord.Embed(
        title="LUHack_Discord_Verification_Bot", description=description, color=0xF60000
    )
    embed.add_field(
        name="L!Help", value="Shows all valid instructions that the bot will accept"
    )
    embed.add_field(
        name="L!Generate_Token <**email**>",
        value="Generates an authentication token, then emails it to the provided email if you aren't already verified. You must provide a valid lancaster email address or you will not get an authentication token",
        inline=True,
    )
    embed.add_field(
        name="L!Verify_Token <**token**>",
        value="Takes an authentication token, checks if it is valid and if so elevates you to Verified LUHacker. Tokens expire after 30 minutes.",
        inline=True,
    )
    await context.send(embed=embed)


# Command that generates and emails a token
@client.command(
    name="Generate_Token",
    description="Generates an authentication token, then emails it to the provided email if you aren't already verified",
    brief="First step on the path to Grand Master Cyber Wizard",
    aliases=[
        "gib_token",
        "i_wanna_be_wizard_too",
        "generate_Token",
        "Generate_token",
        "generate_token",
    ],
)
async def generate_token(context, email: str):
    # Check verified users to see if the person already is verified
    # if database_handler.check_is_verified(context.message.author.id):
    #     # If user is verified then send a message saying that to the user
    #     await context.send("You're already verified")

    # Otherwise check if the provided email is a lancs email
    if email_handler.check_lancs_email(email):
        # Generate authentication token
        auth_token = token_handler.generate_authentication_token(
            context.message.author.id
        )

        # Save email in database
        email_insert_id = database_handler.insert_into_emails(
            email_handler.encrypt_email(email)
        )

        # Save request in database
        request_insert_id = database_handler.insert_into_requests(
            context.message.id,
            context.message.author.name,
            context.author.id,
            email_insert_id,
        )

        # Save token in database
        database_handler.insert_into_tokens(auth_token, request_insert_id)

        # Send email with token
        email_handler.send_email(email, auth_token)
        await context.send(f"A verification email has been sent to: `{email}`")
    # Otherwise tell them they need to provide a valid lancs email
    else:
        await context.send(
            "Please provide a valid lancaster email, such as @lancaster.ac.uk or live.lancs.ac.uk"
        )


@client.command(
    name="Verify_Token",
    description="Takes an authentication token, checks if it is valid and if so elevates you to Verified LUHacker",
    brief="Second step on the path to Grand Master Cyber Wizard",
    aliases=[
        "auth_plz",
        "i_really_wanna_be_wizard",
        "verify_Token",
        "Verify_token",
        "verify_token",
    ],
)
async def verify_token(context, auth_token: str):
    # If token is recognised and in date
    if token_handler.validate_token(auth_token):
        # Token is valid so we need to save the user as a valid user, then elevate their privileges
        # First thing to do is get the RequestID from the token

        request_id = token_handler.get_request_id(auth_token)
        if request_id is None:
            await context.send(
                'Invalid token. Tokens expire after 30 minutes. Please generate a new token using `L!generate_token <email>`')

        # Use the request id to go get the corresponding request
        sql = "SELECT UserID, Username, EmailID FROM Requests WHERE RequestID = %s"
        params = (request_id,)

        [(user_id, username, email_id)] = database_handler.send_select_query(sql, params)

        # Save the information in the verified users database
        database_handler.insert_into_verified_users(user_id, username, email_id)

        # Delete the token from the database so it can't be used again
        sql = "DELETE FROM Tokens WHERE Token = %s"
        params = (auth_token,)
        database_handler.send_delete_query(sql, params)

        # Can only get down here if the person who gave the token is the same as the one who generated it, so can just use message.author.id
        # Change the user permissions to Verified LUHacker
        role = next((discord.utils.get(guild.roles, name="Verified LUHacker") for guild in client.guilds), None)
        member = next((discord.utils.get(guild.members, id=int(user_id)) for guild in client.guilds), None)
        if role is None:
            raise Exception("Verified LUHacker role does not exist")
        if member is None:
            raise Exception("Member does not exist in any guild")
        await member.add_roles(role)
        await context.send(
            'Permissions granted, you can now access all of the discord channels. You are now on the path to Grand Master Cyber Wizard!')
    else:
        await context.send(
            'Invalid token. Tokens expire after 30 minutes. Please generate a new token using `L!generate_token <email>`')


# Functionality that assigns default role to new members
@client.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name="Potential LUHacker")
    await member.add_roles(role)


@client.event
async def on_ready():
    await client.change_presence(activity=discord.Game(name="Hack The IoT Space Bulb"))
    print('-----------Bot Credentials-----------')
    print(f'Name:       {client.user.name}')
    print(f'User ID:    {client.user.id}')
    print(f'Timestamp:  {time.strftime("%Y-%m-%d %H:%M:%S")}')
    print('----------------Logs-----------------')


# Run the client
client.run(TOKEN)
