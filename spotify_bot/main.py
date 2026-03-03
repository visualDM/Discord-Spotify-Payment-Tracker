import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import database
import email_checker
import datetime
import asyncio

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')

# Setup intents
intents = discord.Intents.default()
intents.message_content = True


bot = commands.Bot(command_prefix='!', intents=intents)

@tasks.loop(seconds=60)
async def check_emails_task():
    if not EMAIL_USER or not EMAIL_PASS:
        return
    
    print("Checking emails...")
    transactions = email_checker.check_for_payments(EMAIL_USER, EMAIL_PASS)
    
    for t in transactions:
        member = database.get_member_by_gcash_name(t['name'])
        if member:
            database.add_funds(member['user_id'], t['amount'])
            print(f"Credited {t['amount']} to {member['name']}")
            
            user = bot.get_user(member['user_id'])
            if user:
                try:
                    await user.send(f"Recieved payment of PHP {t['amount']} from GCash ({t['name']}). Account credited!")
                except:
                    pass

@tasks.loop(seconds=3600) # Check every hour
async def auto_advance_task():
    now = datetime.datetime.now()
    current_day = now.day
    current_month_str = now.strftime("%Y-%m")
    
    # We only want to process billing once a day. 
    # Since we check every hour, we just need to rely on the DB check 'last_billed_date'
    # which is handled by get_due_groups.
    
    due_groups = database.get_due_groups(current_day, current_month_str)
    
    for group in due_groups:
        print(f"Auto-advancing group '{group['name']}'...")
        cost = database.process_month_for_group(group['id'])
        database.update_last_billed_date(group['id'], current_month_str)
        
        # Notify negative balances
        await notify_negative_balances(group['id'])





async def notify_negative_balances(group_id, ctx=None):
    members = database.get_members_in_group(group_id)
    group = database.get_group_by_id(group_id)
    
    sender = None
    if ctx:
        sender = ctx
    elif group and group['channel_id']:
        sender = bot.get_channel(group['channel_id'])
    
    mentions = []
    
    for m in members:
        if m['balance'] < 0:
            user = bot.get_user(m['user_id'])
            # If get_user fails (uncached), try fetch_user if possible, or just skip
            if not user:
                try:
                    user = await bot.fetch_user(m['user_id'])
                except:
                    pass
            
            if user:
                mentions.append(user.mention)
                
                # # ALWAYS DM the user
                # try:
                #     gif_url = "https://media1.tenor.com/m/j-w-shg3C3kAAAAC/where-is-the-money-lebowski.gif"
                #     await user.send(f"⚠️ **Insufficient Funds!**\nYour balance is **{m['balance']:.2f}php** in group '{group['name']}'.\nPlease top up immediately!")
                #     await user.send(gif_url)
                # except Exception as e:
                #     print(f"Failed to DM user {m['name']}: {e}")

    # Send public shame message if we have a valid channel context
    if sender and mentions:
        gif_url = "https://tenor.com/view/lebowski-money-toilet-wheres-the-money-lebowski-gif-24292554"
        debtors = ", ".join(mentions)
        try:
            await sender.send(f"⚠️ **Insufficient Funds!**\n{debtors}, you have negative balances! Please top up immediately.")
            await sender.send(gif_url)
        except Exception as e:
            print(f"Failed to send to channel: {e}")

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    database.init_db()
    print("Database initialized.")
    if EMAIL_USER and EMAIL_PASS:
        print("Starting email checker task...")
        check_emails_task.start()
    else:
        print("Email config missing. Email checker disabled.")
    
    print("Starting auto-advance task...")
    auto_advance_task.start()

@bot.command(name='create_family')
async def create_family(ctx, *, name: str):
    """Create a new Spotify Family group."""
    # Capture channel ID
    if database.create_group(name, ctx.channel.id):
        await ctx.send(f"Family group '{name}' created! You can now user `!join \"{name}\"`")
    else:
        await ctx.send(f"A family with the name '{name}' already exists.")

@bot.command(name='join')
async def join_group(ctx, *, family_name: str):
    """Join an existing family group."""
    group = database.get_group_by_name(family_name)
    if not group:
        await ctx.send(f"Family '{family_name}' not found. Check spelling or create it with `!create_family`.")
        return

    if database.add_member(ctx.author.id, ctx.author.display_name, group['id']):
        await ctx.send(f"Welcome to the '{family_name}' family, {ctx.author.mention}!")
    else:
        # Check why they failed
        member = database.get_member(ctx.author.id)
        if member:
            await ctx.send(f"You are already in the '{member['group_name']}' family. You must `!leave` first.")
        else:
            await ctx.send("Could not join group. Unknown error.")

@bot.command(name='leave')
async def leave_group(ctx):
    """Leave your current family."""
    member = database.get_member(ctx.author.id)
    if not member:
        await ctx.send("You are not in any family.")
        return
    
    database.remove_member(ctx.author.id)
    await ctx.send(f"You have left the '{member['group_name']}' family.")

@bot.command(name='delete_family')
async def delete_family(ctx):
    """Delete your family group (Confirmation required)."""
    member = database.get_member(ctx.author.id)
    if not member:
        await ctx.send("You are not in a family.")
        return
    
    group_name = member['group_name']
    await ctx.send(f"⚠️ **WARNING** ⚠️\nAre you sure you want to delete the family **'{group_name}'**?\nThis will remove all members and cannot be undone.\nType `yes` to confirm.")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await bot.wait_for('message', check=check, timeout=30.0)
        if msg.content.lower() == 'yes':
            database.delete_group_cascade(member['group_id'])
            await ctx.send(f"Family group **'{group_name}'** has been deleted.")
        else:
            await ctx.send("Deletion cancelled.")
    except asyncio.TimeoutError:
        await ctx.send("Deletion cancelled (timeout).")

@bot.command(name='status')
async def status(ctx):
    """Show balances of your family members."""
    member = database.get_member(ctx.author.id)
    if not member:
        await ctx.send("You are not in a family. Use `!join <name>`.")
        return
    
    group_id = member['group_id']
    group_cost = member['monthly_cost']
    billing_day = member['billing_day']
    members = database.get_members_in_group(group_id)
    
    embed = discord.Embed(title=f"{member['group_name']} Status", description=f"Monthly Cost: {group_cost}php\nBilling Day: {billing_day}", color=0x1DB954)
    
    for m in members:
        gcash_info = f" ({m['gcash_name']})" if m['gcash_name'] else ""
        embed.add_field(name=f"{m['name']}{gcash_info}", value=f"{m['balance']:.2f}php", inline=False)
    
    # Update channel ID just in case
    database.update_group_channel(group_id, ctx.channel.id)
    
    await ctx.send(embed=embed)

@bot.command(name='pay')
async def pay(ctx, amount: float, member: discord.Member = None):
    """Add funds. Only works for members in YOUR family."""
    caller = database.get_member(ctx.author.id)
    if not caller:
        await ctx.send("You are not in a family.")
        return
    
    target_user = member if member else ctx.author
    target_data = database.get_member(target_user.id)
    
    if not target_data or target_data['group_id'] != caller['group_id']:
        await ctx.send(f"{target_user.mention} is not in your family group.")
        return

    database.add_funds(target_user.id, amount)
    new_bal = database.get_member(target_user.id)['balance']
    await ctx.send(f"Added {amount}php to {target_user.mention}. Balance: {new_bal:.2f}php")

@bot.command(name='cost')
async def set_cost_cmd(ctx, amount: float):
    """Set the monthly deduction cost for YOUR family."""
    caller = database.get_member(ctx.author.id)
    if not caller:
        await ctx.send("You are not in a family.")
        return
    
    database.set_group_cost(caller['group_id'], amount)
    await ctx.send(f"Updated '{caller['group_name']}' monthly cost to {amount}php.")

@bot.command(name='billing_day')
async def set_billing_day_cmd(ctx, day: int):
    """Set the day of the month for auto-deduction (1-31)."""
    caller = database.get_member(ctx.author.id)
    if not caller:
        await ctx.send("You are not in a family.")
        return
    
    if day < 1 or day > 31:
        await ctx.send("Please provide a valid day between 1 and 31.")
        return

    database.set_billing_day(caller['group_id'], day)
    await ctx.send(f"Updated '{caller['group_name']}' billing day to {day}.")

@set_billing_day_cmd.error
async def set_billing_day_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `!billing_day <day>` (e.g., `!billing_day 15`)")

@bot.command(name='advance')
async def advance_month(ctx):
    """Trigger monthly deduction for YOUR family."""
    caller = database.get_member(ctx.author.id)
    if not caller:
        await ctx.send("You are not in a family.")
        return

    # Update channel ID
    database.update_group_channel(caller['group_id'], ctx.channel.id)

    cost = database.process_month_for_group(caller['group_id'])
    
    # Update last billed date to avoid auto-advance triggering again today if they manually advance
    now = datetime.datetime.now()
    database.update_last_billed_date(caller['group_id'], now.strftime("%Y-%m"))

    await ctx.send(f"Processed month for '{caller['group_name']}'. Deducted {cost}php from all members.")
    
    await notify_negative_balances(caller['group_id'], ctx)
    
    await status(ctx)

@bot.command(name='link_gcash')
async def link_gcash(ctx, *, full_name: str):
    """NOT IMPLEMENTED CAUSE FUCK YOU GCASH"""
    caller = database.get_member(ctx.author.id)
    if not caller:
        await ctx.send("Join a family first.")
        return
    
    if database.link_gcash_name(ctx.author.id, full_name):
        await ctx.send(f"Linked GCash name '{full_name}' to {ctx.author.mention}. Future payments will be auto-credited.")
    else:
        await ctx.send(f"The name '{full_name}' is already linked to someone else.")

@bot.command(name='add_users')
async def add_users(ctx, members: commands.Greedy[discord.Member]):
    """Add multiple users to your family. Usage: !add_users @User1 @User2 ..."""
    caller = database.get_member(ctx.author.id)
    if not caller:
        await ctx.send("You are not in a family.")
        return

    if not members:
        await ctx.send("No users mentioned. Usage: `!add_users @User1 @User2`")
        return

    added = []
    failed = []

    for member in members:
        if member.bot:
            failed.append(f"{member.display_name} (Is a bot)")
            continue
            
        if database.add_member(member.id, member.display_name, caller['group_id']):
            added.append(member.mention)
        else:
            # Check why failed
            m = database.get_member(member.id)
            if m:
                failed.append(f"{member.display_name} (Already in '{m['group_name']}')")
            else:
                failed.append(f"{member.display_name} (Unknown error)")

    response = []
    if added:
        response.append(f"✅ Added to '{caller['group_name']}': {', '.join(added)}")
    if failed:
        response.append(f"❌ Failed to add: {', '.join(failed)}")
    
    if response:
        await ctx.send("\n".join(response))
    else:
        await ctx.send("No actions taken.")

if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_TOKEN not found in .env file.")
    else:
        bot.run(TOKEN)
