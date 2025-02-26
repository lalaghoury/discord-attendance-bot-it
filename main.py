import os
from keep_alive import keep_alive
import discord
from discord.ext import commands, tasks
import pandas as pd
from datetime import datetime, timedelta
import sys

print("Python Version:", sys.version)

# Intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

# Bot Setup
TOKEN = os.getenv("TOKEN")
ATTENDANCE_CHANNEL_ID = 1000096920200556675
bot = commands.Bot(command_prefix="!", intents=intents)

# Dictionary to store employee check-ins
attendance_data = {}

# File to store employee records
FILE_NAME = "attendance.csv"

# Load existing data
try:
    df = pd.read_csv(FILE_NAME)
except FileNotFoundError:
    df = pd.DataFrame(
        columns=["Employee", "Date", "In_Time", "Out_Time", "Hours_Worked"])


# Helper function to save data
def save_data():
    df.to_csv(FILE_NAME, index=False)


# Employee Check-in
@bot.event
async def on_message(message):
    if message.author.bot:  # Ignore bot messages
        return

    user = str(message.author)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date = datetime.now().strftime("%Y-%m-%d")

    if message.content.lower() in ["i am in", "in"]:
        # Allow multiple check-ins but prevent if already checked in without a check-out
        if user in attendance_data and attendance_data[user][
                "in_time"] and not attendance_data[user]["out_time"]:
            await message.channel.send(
                f"{user}, you are already checked in! Check out before checking in again."
            )
        else:
            attendance_data[user] = {"in_time": now, "out_time": None}
            await message.channel.send(f"{user} checked in at {now}")

    elif message.content.lower() in ["i am out", "out"]:
        if user not in attendance_data or not attendance_data[user]["in_time"]:
            await message.channel.send(f"{user}, you haven't checked in today!"
                                       )
        elif attendance_data[user]["out_time"] is not None:
            await message.channel.send(
                f"{user}, you have already checked out! Check in before checking out again."
            )
        else:
            in_time = datetime.strptime(attendance_data[user]["in_time"],
                                        "%Y-%m-%d %H:%M:%S")
            out_time = datetime.now()
            hours_worked = (out_time -
                            in_time).total_seconds() / 3600  # Convert to hours
            attendance_data[user]["out_time"] = out_time.strftime(
                "%Y-%m-%d %H:%M:%S")

            # Store in DataFrame
            global df
            new_entry = pd.DataFrame([{
                "Employee":
                user,
                "Date":
                date,
                "In_Time":
                attendance_data[user]["in_time"],
                "Out_Time":
                attendance_data[user]["out_time"],
                "Hours_Worked":
                round(hours_worked, 2)
            }])
            df = pd.concat([df, new_entry], ignore_index=True)

            save_data()  # Save updated data to CSV

            # Reset employee status to allow new check-in
            attendance_data[user] = {"in_time": None, "out_time": None}

            await message.channel.send(
                f"{user} checked out at {out_time.strftime('%Y-%m-%d %H:%M:%S')}. Hours Worked: {round(hours_worked, 2)}"
            )

    await bot.process_commands(message)


# Weekly Report (Command)
@bot.command()
async def weekly_report(ctx):
    report_message = generate_weekly_report()
    await ctx.send(report_message)


# Function to Generate Weekly Report
def generate_weekly_report():
    today = datetime.now()
    start_date = today - timedelta(
        days=today.weekday())  # Get Monday of the current week
    end_date = start_date + timedelta(days=4)  # Get Friday

    # Filter only Monday to Friday records
    df_filtered = df[(df["Date"] >= start_date.strftime("%Y-%m-%d"))
                     & (df["Date"] <= end_date.strftime("%Y-%m-%d"))]

    # Summarize total hours per employee
    weekly_report = df_filtered.groupby(
        "Employee")["Hours_Worked"].sum().reset_index()

    # Generate report message
    report_message = "**📊 Weekly Work Report 📊**\n"
    if weekly_report.empty:
        report_message += "No records found for this week."
    else:
        for _, row in weekly_report.iterrows():
            employee = row["Employee"]
            hours_worked = row["Hours_Worked"]
            if hours_worked >= 40:
                report_message += f"✅ {employee} worked {hours_worked:.2f} hours. Great Job!\n"
            else:
                report_message += f"⚠️ {employee} worked only {hours_worked:.2f} hours. Minimum required: 40.\n"

    return report_message


# Auto-Generate Weekly Report Every Friday
@tasks.loop(hours=168)  # Runs every 7 days
async def auto_weekly_report():
    today = datetime.now()
    if today.weekday() == 4 and today.hour == 18:  # Runs every Friday at 6 PM
        channel = bot.get_channel(
            ATTENDANCE_CHANNEL_ID)  # Replace with actual channel ID
        if channel:
            await channel.send(generate_weekly_report())


@bot.event
async def on_ready():
    print(f"{bot.user} is online!")
    auto_weekly_report.start()  # Start automatic weekly report


# Keep bot alive (For Replit)
keep_alive()

# Run Bot
bot.run(TOKEN)
