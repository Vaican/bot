import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, time
import pytz

# Create bot object with command prefix
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Raid information
FIELD_RAIDS = {
    122: {"name": "Demon Venoma", "location": "Fields of Massacre"},
    124: {"name": "Avenger Graff", "location": "Cemetery"},
    126: {"name": "Lunatic Kulan", "location": "Hot Springs"},
    128: {"name": "Arrogant Lebruum", "location": "Wall of Argos"}
}

# Fixed boss spawn times in Greek time
FIXED_BOSSES = {
    'Swamp Raid': [
        time(15, 0),   # 15:00 Greek time
        time(18, 0),   # 18:00 Greek time
        time(22, 0)    # 22:00 Greek time
    ],
    'Chaos Golem 17 in Pavel Ruins': [
        time(16, 0)    # 16:00 Greek time - once per day
    ],
    'Chaos Golem 18 in Pavel Ruins': [
        time(20, 0)    # 20:00 Greek time - once per day
    ]
}

# Dictionary to store raid details: level -> (time_of_death, notification_sent)
raids = {}

# Greek timezone
GREEK_TZ = pytz.timezone('Europe/Athens')

# Channel and role details
RAID_CHANNEL = 'raid-channel'  # Channel name for raid notifications
RAID_ROLE = 'Raid'  # Role to notify

# Helper function to notify all members with a specific role
async def notify_role(channel, role_name, message):
    raid_role = discord.utils.get(channel.guild.roles, name=role_name)
    if raid_role:
        await channel.send(f"{raid_role.mention} {message}")
    else:
        await channel.send(f"Role '{role_name}' not found in this server.")

# Command to handle raid timers
@bot.command(name='raid')
async def raid_command(ctx, *, raid_input: str):
    # Only allow the command in the 'raid-channel'
    if ctx.channel.name != RAID_CHANNEL:
        await ctx.send("This command can only be used in the raid-channel.")
        return

    # Parse the command to check for time adjustment
    command_parts = raid_input.split('-')
    try:
        level = int(command_parts[0])
        if level not in FIELD_RAIDS:
            await ctx.send(f"Invalid raid level: {level}.")
            return
    except ValueError:
        await ctx.send("Invalid command format. Use !raid <level> or !raid <level>-<minutes>.")
        return

    time_adjustment = 0
    if len(command_parts) > 1:
        try:
            time_adjustment = int(command_parts[1])
        except ValueError:
            await ctx.send("Invalid time adjustment. Please use a number.")
            return

    # Calculate the adjusted respawn time
    adjusted_respawn_time = timedelta(minutes=300 - time_adjustment)
    death_time = datetime.now(GREEK_TZ)

    # Update or create the raid entry
    raids[level] = {
        'death_time': death_time,
        'respawn_time': adjusted_respawn_time,
        'notifications_sent': False
    }

    raid_info = FIELD_RAIDS[level]
    await ctx.send(
        f"Field Raid {raid_info['name']} (Level {level}) has just died! "
        f"Respawn in {300 - time_adjustment} minutes at {raid_info['location']}."
    )

# Command to display all field boss timers
@bot.command(name='timer')
async def timer_command(ctx):
    message_content = "Field Boss Timers:\n"
    for level, raid_data in raids.items():
        raid_info = FIELD_RAIDS[level]
        time_remaining = (raid_data['death_time'] + raid_data['respawn_time']) - datetime.now(GREEK_TZ)
        minutes_remaining = int(time_remaining.total_seconds() // 60)
        hours, minutes = divmod(minutes_remaining, 60)
        message_content += (
            f"Location: {raid_info['location']} | Level: {level}\n"
            f"Boss: {raid_info['name']}\n"
            f"Countdown: {minutes_remaining} minutes ({hours} hours {minutes} minutes)\n\n"
        )
    await ctx.send(message_content)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    check_raid_responses.start()  # Start the timer task
    update_sticky_message.start()  # Start the sticky message update task
    check_fixed_bosses.start()  # Start the fixed bosses notification task

# Task that checks for raids and sends notifications
@tasks.loop(seconds=10)  # Check every 10 seconds
async def check_raid_responses():
    current_time = datetime.now(GREEK_TZ)

    # Handle dynamic raids
    for level, raid_data in list(raids.items()):
        death_time = raid_data['death_time']
        respawn_time = death_time + raid_data['respawn_time']
        time_remaining = respawn_time - current_time
        raid_info = FIELD_RAIDS[level]

        if timedelta(minutes=10) <= time_remaining <= timedelta(minutes=10, seconds=10):
            if not raid_data['notifications_sent']:
                channel = discord.utils.get(bot.get_all_channels(), name=RAID_CHANNEL)
                if channel:
                    await notify_role(
                        channel,
                        RAID_ROLE,
                        f"Field Raid {raid_info['name']} (Level {level}) will respawn in 10 minutes at {raid_info['location']}!"
                    )
                    raid_data['notifications_sent'] = True

        if timedelta(minutes=5) <= time_remaining <= timedelta(minutes=5, seconds=10):
            if not raid_data['notifications_sent']:
                channel = discord.utils.get(bot.get_all_channels(), name=RAID_CHANNEL)
                if channel:
                    await notify_role(
                        channel,
                        RAID_ROLE,
                        f"Field Raid {raid_info['name']} (Level {level}) will respawn in 5 minutes at {raid_info['location']}!"
                    )
                    raid_data['notifications_sent'] = True

        if time_remaining <= timedelta(0):
            channel = discord.utils.get(bot.get_all_channels(), name=RAID_CHANNEL)
            if channel:
                await notify_role(
                    channel,
                    RAID_ROLE,
                    f"Field Raid {raid_info['name']} (Level {level}) has respawned at {raid_info['location']}!"
                )
            raids.pop(level)

# Task to update the sticky message
@tasks.loop(minutes=1)  # Update every minute
async def update_sticky_message():
    channel = discord.utils.get(bot.get_all_channels(), name=RAID_CHANNEL)
    if channel:
        message_content = "Field Boss Timers:\n"
        for level, raid_data in raids.items():
            raid_info = FIELD_RAIDS[level]
            time_remaining = (raid_data['death_time'] + raid_data['respawn_time']) - datetime.now(GREEK_TZ)
            minutes_remaining = int(time_remaining.total_seconds() // 60)
            hours, minutes = divmod(minutes_remaining, 60)
            message_content += (
                f"Location: {raid_info['location']} | Level: {level}\n"
                f"Boss: {raid_info['name']}\n"
                f"Countdown: {minutes_remaining} minutes ({hours} hours {minutes} minutes)\n\n"
            )
        # Send or edit the sticky message
        async for message in channel.history(limit=10):
            if message.author == bot.user and "Field Boss Timers:" in message.content:
                await message.edit(content=message_content)
                break
        else:
            await channel.send(message_content)

# Task to check fixed bosses and send notifications
@tasks.loop(seconds=60)  # Check every minute
async def check_fixed_bosses():
    current_time = datetime.now(GREEK_TZ).time()
    channel = discord.utils.get(bot.get_all_channels(), name=RAID_CHANNEL)

    for boss_name, spawn_times in FIXED_BOSSES.items():
        for spawn_time in spawn_times:
            five_minutes_before = (datetime.combine(datetime.today(), spawn_time) - timedelta(minutes=5)).time()

            # 5-minute warning
            if five_minutes_before <= current_time <= (datetime.combine(datetime.today(), five_minutes_before) + timedelta(seconds=60)).time():
                if channel:
                    await notify_role(channel, RAID_ROLE, f"Reminder: {boss_name} will spawn in 5 minutes!")

            # Spawn notification
            if spawn_time <= current_time <= (datetime.combine(datetime.today(), spawn_time) + timedelta(seconds=60)).time():
                if channel:
                    await notify_role(channel, RAID_ROLE, f"{boss_name} has spawned!")

# Run the bot
bot.run("MTMxMDcxOTEyMTIyNjIwMzI3OA.GDmAeL.BXRFMytqdzWliCvZugt0nAS4T6K-Ooh")
