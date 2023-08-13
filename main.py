import discord
from discord.ext import commands
import xxhash
import requests
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
#import time

sessionid = {'sessionid':'INSTAGRAM-SESSION-ID-HERE'} #To access public Instagram endpoint without being IP blocked

cred = credentials.Certificate('./influencerdiscord-aafdfbffb7e3.json') # This json file is automatically generated in Google Cloud when creating the IAM email account for the Google Cloud project associated with the Firebase project
firebase_admin.initialize_app(cred)

db = firestore.client()
verifications = db.collection(u'verifications')

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix = '!', intents=intents)
client.remove_command("help")

def usernameExists(username):
    #check if this username exists
    r = requests.get("https://www.instagram.com/" + username + "/?__a=1", cookies=sessionid) #public non-official endpoint. should use official authenticated endpoint in the future
    try:
        r = r.json()
        try:
            userID = r['logging_page_id'].replace('profilePage_','')
            return userID
        except:
            return False
    except: #If it errors trying to interpret json, that means instagram redirected to 404 HTML page instead of presenting json object of the user
        return False

def genKey(message):
    hash = xxhash.xxh32(message) #Maybe add a time-based seed
    key = 'verify' + hash.hexdigest()
    return key

def checkBio(userID, discordUID):
    username = getUsername(userID)
    if username == False: #probably got banned
        return False
    r = requests.get("https://www.instagram.com/" + username + "/?__a=1", cookies=sessionid).json()
    bio = r['graphql']['user']['biography']
    if genKey(userID+discordUID) in bio:
        return True
    else:
        return False

def plaintext(message):
    #add more discord markdown to make bulletproof
    if message.startswith('_') and message.endswith('_'):
        message = message.replace('_','\_')
    return message

def getUsername(userID):
    username = ''
    if userID:
        #valid user-agent
        headers = {
            'user-agent':'Mozilla/5.0 (Linux; Android 10; Pixel 3a XL Build/QQ3A.200605.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/83.0.4103.106 Mobile Safari/537.36 Instagram 149.0.0.25.120 Android (29/10; 400dpi; 1080x2120; Google/google; Pixel 3a XL; bonito; bonito; en_US; 228970707)'
        }
        try:
            r = requests.get('https://i.instagram.com/api/v1/users/' + userID + '/info/', headers=headers, cookies=sessionid).json()
            username = r['user']['username']
            return username
        except Exception as e: #probably got banned, so it returns a 404 page
            print("Getting user failed due to '{}'".format(e))
            return False

def userInfo(userID):
    username = getUsername(userID)
    if username == False: #probably got banned
        return False
    r = requests.get("https://www.instagram.com/" + username + "/?__a=1", cookies=sessionid).json()
    return r

def userFollowers(userID):
    userIDInfo = userInfo(userID)
    if userIDInfo != False:
        followers = userIDInfo['graphql']['user']['edge_followed_by']['count']
        return followers
    else: #probably got banned
        return False

def totalFollowers(instagram):
    followers = 0
    verified = False #Make sure it doesn't return 0 followers if there are no verified accounts
    userIDs = instagram['instagram']
    for userID in userIDs:
        if userIDs[userID] == True:
            verified = True
            userIDFollowers = userFollowers(userID)
            if userIDFollowers != False:
                followers += userIDFollowers
    if verified == True:
        return followers
    else:
        return False

def findRole(ctx,followers):
    if followers < 1000:
        role = discord.utils.get(ctx.author.guild.roles, name="0 to 1,000 Followers")
    elif followers < 5000:
        role = discord.utils.get(ctx.author.guild.roles, name="1,000 to 5,000 Followers")
    elif followers < 10000:
        role = discord.utils.get(ctx.author.guild.roles, name="5,000 to 10,000 Followers")
    elif followers < 50000:
        role = discord.utils.get(ctx.author.guild.roles, name="10,000 to 50,000 Followers")
    elif followers < 100000:
        role = discord.utils.get(ctx.author.guild.roles, name="50,000 to 100,000 Followers")
    elif followers < 500000:
        role = discord.utils.get(ctx.author.guild.roles, name="100,000 to 500,000 Followers")
    elif followers < 1000000:
        role = discord.utils.get(ctx.author.guild.roles, name="500,000 to 1,000,000 Followers")
    elif followers < 5000000:
        role = discord.utils.get(ctx.author.guild.roles, name="1,000,000 to 5,000,000 Followers")
    elif followers < 10000000:
        role = discord.utils.get(ctx.author.guild.roles, name="5,000,000 to 10,000,000 Followers")
    return role

@client.event
async def on_ready():
    print('Bot is ready.')

@client.command()
async def verify(ctx, username, blank=""): #make it say youre already verified if you are. or remove rank when you say !verify
    if blank == "":
        username = username.lower()
        plainUsername = plaintext(username)
        userID = usernameExists(username) #Instagram userID
        if userID != False:
            key = genKey(userID + str(ctx.author.id))
            verifications.document(str(ctx.author.id)).set({u'instagram':{userID:False}},merge=True)
            await ctx.send(ctx.author.mention + " Add this verification code to " + plainUsername + "'s bio, then say !done when you're done: " + key) #make a private username-database of unverified usernames that !done checks. purge unverified usernames after 1 day
        else:
            await ctx.send("Sorry " + ctx.author.mention + ", I can't find the Instagram user " + plainUsername + ".")
    else: #The user passed more than one argument to this function
        await ctx.send("Hey " + ctx.author.mention + ", please enter the username without any spaces.")

@client.command()
async def done(ctx):
    instagram = verifications.document(str(ctx.author.id)).get().to_dict()
    if instagram != None:
        userIDs = instagram['instagram']
        for userID in userIDs:
            if userIDs[userID] == False:
                verified = checkBio(userID,str(ctx.author.id))
                if verified == True:
                    verifications.document(str(ctx.author.id)).set({u'instagram':{userID:True}},merge=True)
                    await ctx.send(ctx.author.mention + " Verified " + plaintext(getUsername(userID)))
                elif verified == False: #User got banned so delete it
                    verifications.document(str(ctx.author.id)).update({'instagram.'+userID:firestore.DELETE_FIELD})
                    await ctx.send(ctx.author.mention + " The Instagram account with a user ID of " + str(userID) + " is likely banned, deleting...")
                else:
                    await ctx.send(ctx.author.mention + " Couldn't find verification code in the bio of " + plaintext(getUsername(userID)))
        for userRole in ctx.author.roles:
            if str(userRole) != "@everyone":
                await ctx.author.remove_roles(userRole) #Remove their ranks before setting new ones. Not good if user has other roles like scleptic
        instagram = verifications.document(str(ctx.author.id)).get().to_dict() #Get our newly updated data
        followers = totalFollowers(instagram)
        if followers != False:
            role = findRole(ctx,followers)
            await ctx.author.add_roles(role)
    else:
        await ctx.send(ctx.author.mention + " Please say !verify <instagram username> before saying !done")

@client.command()
async def unverify(ctx, username, blank=""):
    if blank =="":
        userID = usernameExists(username)
        verifications.document(str(ctx.author.id)).update({'instagram.'+userID:firestore.DELETE_FIELD})
        await ctx.send(ctx.author.mention + ' Successfully disassociated ' + plaintext(username))
        for userRole in ctx.author.roles:
            if str(userRole) != "@everyone":
                await ctx.author.remove_roles(userRole)
        instagram = verifications.document(str(ctx.author.id)).get().to_dict()
        if instagram != None: #If there are no verified accounts left, the person should have no rank anymore.
            followers = totalFollowers(instagram)
            if followers != False: #They had no verified accounts if this is False
                role = findRole(ctx,followers)
                await ctx.author.add_roles(role)
    else:
        await ctx.send("Hey " + ctx.author.mention + ", please enter the username without any spaces.")

@client.command()
async def accounts(ctx):
    if len(ctx.message.mentions) == 0:
        allAccounts = verifications.document(str(ctx.author.id)).get().to_dict()['instagram']
        accountsReply = ctx.author.mention + ' Your verified accounts are: ' #Only reply with verified accounts
    else:
        allAccounts = verifications.document(str(ctx.message.mentions[0].id)).get().to_dict()['instagram']
        accountsReply = ctx.author.mention + ' The verified accounts for ' + ctx.message.mentions[0].mention + ' are: '
    for account in allAccounts:
        if allAccounts[account] == True:
            username = getUsername(account)
            if username != False:
                accountsReply = accountsReply + '\n' + plaintext(username)
            else: #Account probably got banned, so delete it.
                if len(ctx.message.mentions) == 0:
                    verifications.document(str(ctx.author.id)).update({'instagram.'+account:firestore.DELETE_FIELD})
                else:
                    verifications.document(str(ctx.message.mentions[0].id)).update({'instagram.'+account:firestore.DELETE_FIELD})
    await ctx.send(accountsReply)

@client.command()
async def update(ctx):
    #Should other users be able to update others' ranks?
    for userRole in ctx.author.roles:
        if str(userRole) != "@everyone":
            await ctx.author.remove_roles(userRole)
    instagram = verifications.document(str(ctx.author.id)).get().to_dict()
    if instagram != None: #If there are no verified accounts left, the person should have no rank anymore.
        followers = totalFollowers(instagram)
        if followers != False: #They had no verified accounts if this is False
            role = findRole(ctx,followers)
            await ctx.author.add_roles(role)
            await ctx.send(ctx.author.mention + " You have a verified total of " + str(followers) + " followers. Your rank is " + role.name)
        else:
            await ctx.send(ctx.author.mention + " It looks like you have not verified any of your added accounts.")
    else:
        await ctx.send(ctx.author.mention + " It looks like you have not added any accounts.")

@client.command()
async def help(ctx):
    await ctx.send(ctx.author.mention + "\nSay !verify <instagram-username> to add an Instagram account\nSay !done to confirm verification codes\nSay !unverify <instagram-username> to remove an Instagram account\nSay !accounts to view your verified Instagram accounts\nSay !accounts @<tag-discord-user> to view someone else's verified Instagram accounts\nSay !update to update your rank according to the number of followers you have")

@client.command()
async def test(ctx):
    await ctx.send("TEST")

client.run('DISCORD-BOT-TOKEN-HERE')
