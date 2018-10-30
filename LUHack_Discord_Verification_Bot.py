# Created by DethMetalDuck
# LUHack_Discord_Verification_Bot contains the main logic for the bot

import discord
from discord import Game
from discord.ext.commands import Bot
import Misc_Functionality
import Database_Handler
import Email_Handler
import Token_Handler
from secrets import bot_client_token

# TODO Add anti-yoghurt functionality
# TODO Come up with better ways to use keys instead of hard coding
# TODO Add easter eggs

# Secret client token :^)
TOKEN = bot_client_token

# Initialise discord client
client = Bot(command_prefix='L!', pm_help=True)

# Remove default help command so we can write our own
client.remove_command('help')


# Help command
@client.command(name='Help',
                description="Provides a list of available commands",
                brief="For when you have no idea what's going on",
                aliases=['help', 'info', 'Info', 'nani_the_fuck'],
                pass_context=True)
async def help(context):
    description = "An autonomous entity, forged in the magical fires of the IoT Space Bulb. Interact with this wonderous construct using: "
    embed = discord.Embed(title="LUHack_Discord_Verification_Bot", description=description, color=0xf60000)
    embed.add_field(name="L!Help", value="Shows all valid instructions that the bot will accept")
    embed.add_field(name="L!Generate_Token <**email**>", value="Generates an authentication token, then emails it to the provided email if you aren't already verified. You must provide a valid lancaster email address or you will not get an authentication token", inline=True)
    embed.add_field(name="L!Verify_Token <**token**>", value="Takes an authentication token, checks if it is valid and if so elevates you to Verified LUHacker", inline=True)
    await client.say(embed=embed)


# Command that generates and emails a token
@client.command(name='Generate_Token',
                description="Generates an authentication token, then emails it to the provided email if you aren't already verified",
                brief="First step on the path to Grand Master Cyber Wizard",
                aliases=['gib_token', 'i_wanna_be_wizard_too', 'generate_Token', 'Generate_token', 'generate_token'],
                pass_context=True)
async def generate_token(context, email: str):
    # Check verified users to see if the person already is verified
    if Database_Handler.check_is_verified(context.message.author.id):
        # If user is verified then send a message saying that to the user
        user = discord.utils.get(client.get_all_members(), id=context.message.author.id)
        if user is not None:
            try:
                await client.say("You're already verified")

                # This is literally to silence an error that was being annoying
            except:
                x = 1
    # Otherwise check if the provided email is a lancs email
    elif Email_Handler.check_lancs_email(email):
        # Generate authentication token
        auth_token = Token_Handler.generate_authentication_token(context.message.author.id)

        # Save email in database
        email_insert_id = Database_Handler.insert_into_emails(Email_Handler.encrypt_email(email))

        # Setup for saving request
        request_values = (context.message.id, context.message.author.name, context.message.author.id, email_insert_id)

        # Save request in database
        request_insert_id = Database_Handler.insert_into_requests(request_values)

        # Setup for saving Token in database
        token_values = (auth_token, request_insert_id)

        # Save token in database
        Database_Handler.insert_into_tokens(token_values)

        # Send email with token
        Email_Handler.send_email(email, auth_token)
    # Otherwise tell them they need to provide a valid lancs email
    else:
        user = discord.utils.get(client.get_all_members(), id=context.message.author.id)
        if user is not None:
            try:
                await client.say("Please provide a valid lancaster email, such as @lancaster.ac.uk or live.lancs.ac.uk")

                # This is literally to silence an error that was being annoying
            except:
                x = 1



@client.command(name='Verify_Token',
                description="Takes an authentication token, checks if it is valid and if so elevates you to Verified LUHacker",
                brief="Second step on the path to Grand Master Cyber Wizard",
                aliases=['auth_plz', 'i_really_wanna_be_wizard', 'verify_Token', 'Verify_token', 'verify_token'],
                pass_context=True)
async def verify_token(context, auth_token: str):
    # Sanitise the token input
    sanitised_token = Token_Handler.sanitise_input(auth_token)

    # If token is recognised and in date
    if Token_Handler.validate_token(sanitised_token, context.message.author.id):
        # Token is valid so we need to save the user as a valid user, then elevate their privileges
        # First thing to do is get the RequestID from the token

        request_id = Token_Handler.get_request_id(sanitised_token)

        # Use the request id to go get the corresponding request
        sql = 'SELECT * FROM Requests WHERE RequestID = %d' % request_id
        request = Database_Handler.send_select_query(sql)

        # Request will contain (RequestID, MessageID, Username, UserID, CreationDate, EmailID)
        # To save in verified users, need userID, username, EmailID
        verified_users_values = ((request[0])[3], (request[0])[2], (request[0])[5])

        # Save the information in the verified users database
        Database_Handler.insert_into_verified_users(verified_users_values)

        # Delete the token from the database so it can't be used again
        sql = 'DELETE FROM Tokens WHERE Token = \"%s\"' % sanitised_token
        Database_Handler.send_delete_query(sql)

        # Can only get down here if the person who gave the token is the same as the one who generated it, so can just use message.author.id
        # Change the user permissions to Verified LUHacker
        user = discord.utils.get(client.get_all_members(), id=context.message.author.id)
        for server in client.servers:
            for role in server.roles:
                if role.name == "Verified LUHacker":
                    await client.add_roles(user, role)
                #if role.name == "Potential LUHacker":
                #    await client.remove_roles(user, role)

        await client.say('Accepted, you are now on the path to Grand Master Cyber Wizard!')
    else:
        await client.say('Rejected')


# Functionality that assigns default role to new members
@client.event
async def on_member_join(member):
    for server in client.servers:
        for role in server.roles:
            if role.name == "Potential LUHacker":
                await client.add_roles(member, role)


@client.event
async def on_ready():
    await client.change_presence(game=Game(name="Hack The IoT Space Bulb"))
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')


# Run the client
client.run(TOKEN)
