import os, random, asyncio, logging
from html import escape
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

MAX = 4
JOIN_TIME = 120
GAMES = {}

def S(cid):
    return GAMES.setdefault(cid, {"game":None,"host":None,"players":[],"d":{},"task":None})

def mention(uid,name):
    return f'<a href="tg://user?id={uid}"><b>{escape(name)}</b></a>'

def reset(cid):
    s=S(cid)
    if s.get("task"):
        try: s["task"].cancel()
        except: pass
    GAMES[cid]={"game":None,"host":None,"players":[],"d":{},"task":None}

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🃏 UNO",callback_data="m:uno"),
         InlineKeyboardButton("🔤 WORD",callback_data="m:word")],
        [InlineKeyboardButton("🏏 CRICKET",callback_data="m:cricket"),
         InlineKeyboardButton("🎲 LUDO",callback_data="m:ludo")],
        [InlineKeyboardButton("🏆 LEADERBOARD",callback_data="m:lb")]
    ])

def lobby(game):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🟢 JOIN {game.upper()}",callback_data=f"join:{game}")],
        [InlineKeyboardButton("⚡ FORCE START",callback_data=f"force:{game}")],
        [InlineKeyboardButton("🚪 LEAVE",callback_data=f"leave:{game}")]
    ])

STICKERS={}

async def start(u,c):
    if u.effective_chat.type=="private":
        await u.message.reply_text("👋 Add me to a group. Games are group-only.")
        return
    await u.message.reply_text("🎮 <b>CC GAMING</b>\n\n🃏 UNO • 🔤 WORD • 🏏 CRICKET • 🎲 LUDO",
                              parse_mode="HTML",reply_markup=menu())

async def menu_cmd(u,c):
    if u.effective_chat.type!="private":
        await u.message.reply_text("🎮 <b>CC GAMING MENU</b>",parse_mode="HTML",reply_markup=menu())

async def begin(u,c,game):
    if u.effective_chat.type=="private": return
    cid=u.effective_chat.id; s=S(cid)
    if s["game"]:
        await u.message.reply_text(f"🔒 <b>{s['game'].upper()}</b> match already running.",parse_mode="HTML"); return
    s["game"]=game;s["host"]=u.effective_user.id
    s["players"]=[{"id":u.effective_user.id,"name":u.effective_user.full_name}]
    s["d"]={"phase":"join"}
    await u.message.reply_text(f"🎮 <b>{game.upper()} LOBBY</b>\n\n👥 Max: {MAX}\n⏱️ {JOIN_TIME} seconds\n\nJoin below 👇",
                               parse_mode="HTML",reply_markup=lobby(game))
    s["task"]=asyncio.create_task(auto(c,cid,game))

async def auto(ctx,cid,game):
    try: await asyncio.sleep(JOIN_TIME)
    except asyncio.CancelledError: return
    s=GAMES.get(cid)
    if not s or s["game"]!=game:return
    if len(s["players"])<2:
        await ctx.bot.send_message(cid,"⏰ Lobby closed. Minimum 2 players required.")
        reset(cid);return
    await launch(ctx,cid,game)

async def launch(ctx,cid,game):
    if game=="uno": await uno_launch(ctx,cid)
    elif game=="word": await word_launch(ctx,cid)
    elif game=="cricket": await cricket_launch(ctx,cid)
    elif game=="ludo": await ludo_launch(ctx,cid)

# ---------------- UNO ----------------

def deck():
    a=[]; cs=["Red","Yellow","Green","Blue"]
    for col in cs:
        a.append((col,"0"))
        for n in range(1,10):
            for _ in range(2): a.append((col,str(n)))
        for v in ["Skip","Reverse","Draw Two"]:
            for _ in range(2): a.append((col,v))
    for _ in range(4): a += [("Wild","Wild"),("Wild","Wild Draw Four")]
    random.shuffle(a);return a

def ce(c): return {"Red":"🔴","Yellow":"🟡","Green":"🟢","Blue":"🔵","Wild":"🌈"}[c]
def cn(x): return f"{ce(x[0])} {x[0]} {x[1]}"
def uk(x): return x[0].upper()+"_"+x[1].upper().replace(" ","_")

def ucur(d): return d["order"][d["turn"]]
def playable(x,d):
    return x[0]=="Wild" or x[0]==d["color"] or x[1]==d["discard"][-1][1]

async def uno_launch(ctx,cid):
    s=S(cid); d=s["d"]; d["order"]=[p["id"] for p in s["players"]]
    d["names"]={p["id"]:p["name"] for p in s["players"]};d["hands"]={p:[] for p in d["order"]}
    d["deck"]=deck();d["discard"]=[];d["turn"]=0;d["dir"]=1;d["phase"]="live"
    for p in d["order"]: d["hands"][p]=[d["deck"].pop() for _ in range(7)]
    while True:
        x=d["deck"].pop()
        if x[1] in ["Skip","Reverse","Draw Two","Wild","Wild Draw Four"]:
            d["deck"].insert(0,x);random.shuffle(d["deck"]);continue
        d["discard"]=[x];d["color"]=x[0];break
    await ctx.bot.send_message(cid,"🔥 <b>UNO MATCH STARTED!</b>\n💬 Gameplay stays in this group.",parse_mode="HTML")
    await uno_refresh(ctx,cid);await uno_turn(ctx,cid)

async def uno_refresh(ctx,cid):
    s=S(cid);d=s["d"]
    for p in d["order"]:
        bs=[]
        for i,x in enumerate(d["hands"][p]):
            label=("▶️ " if p==ucur(d) and playable(x,d) else "")+cn(x)
            bs.append(InlineKeyboardButton(label,callback_data=f"u:p:{cid}:{p}:{i}"))
        rows=[bs[i:i+2] for i in range(0,len(bs),2)]
        rows.append([InlineKeyboardButton("🎴 DRAW",callback_data=f"u:d:{cid}:{p}"),
                     InlineKeyboardButton("📢 UNO!",callback_data=f"u:n:{cid}:{p}")])
        await ctx.bot.send_message(cid,f"🃏 {mention(p,d['names'][p])} — <b>{len(d['hands'][p])} cards</b>",
                                   parse_mode="HTML",reply_markup=InlineKeyboardMarkup(rows))

async def uno_turn(ctx,cid):
    s=S(cid);d=s["d"];p=ucur(d)
    await ctx.bot.send_message(cid,f"🎯 <b>UNO TURN</b>\n\n👤 {mention(p,d['names'][p])}\n"
                                   f"🃏 Top: <b>{cn(d['discard'][-1])}</b>\n"
                                   f"🎨 {ce(d['color'])} <b>{d['color']}</b>\n\n🔥 YOUR TURN!",
                                   parse_mode="HTML")

async def uno_play(q,ctx,cid,p,i):
    if q.from_user.id!=p: await q.answer("❌ Not your cards!",show_alert=True);return
    s=S(cid);d=s["d"]
    if d.get("phase")!="live" or ucur(d)!=p: await q.answer("⏳ Not your turn!",show_alert=True);return
    h=d["hands"][p]
    if i>=len(h): return
    x=h[i]
    if not playable(x,d): await q.answer("❌ Cannot play.",show_alert=True);return
    h.pop(i);d["discard"].append(x)
    fid=STICKERS.get(uk(x))
    if fid:
        try: await ctx.bot.send_sticker(cid,fid)
        except: await ctx.bot.send_message(cid,f"🃏 {mention(p,d['names'][p])} played <b>{cn(x)}</b>",parse_mode="HTML")
    else: await ctx.bot.send_message(cid,f"🃏 {mention(p,d['names'][p])} played <b>{cn(x)}</b>",parse_mode="HTML")
    if len(h)==0:
        d["phase"]="done";await ctx.bot.send_message(cid,f"🏆 <b>UNO WINNER!</b>\n👑 {mention(p,d['names'][p])}",parse_mode="HTML");reset(cid);return
    if len(h)==1: await ctx.bot.send_message(cid,f"🚨 {mention(p,d['names'][p])} has ONE CARD! 📢 UNO!",parse_mode="HTML")
    if x[0]=="Wild":
        await q.answer("🌈 Choose colour")
        await ctx.bot.send_message(cid,f"🌈 {mention(p,d['names'][p])} choose colour:",parse_mode="HTML",
          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔴 RED",callback_data=f"u:c:{cid}:{p}:Red"),
                                               InlineKeyboardButton("🟡 YELLOW",callback_data=f"u:c:{cid}:{p}:Yellow")],
                                              [InlineKeyboardButton("🟢 GREEN",callback_data=f"u:c:{cid}:{p}:Green"),
                                               InlineKeyboardButton("🔵 BLUE",callback_data=f"u:c:{cid}:{p}:Blue")]]));return
    d["color"]=x[0]
    if x[1]=="Skip": d["turn"]=(d["turn"]+2*d["dir"])%len(d["order"])
    elif x[1]=="Reverse":
        d["dir"]*=-1;d["turn"]=(d["turn"]+d["dir"])%len(d["order"])
    elif x[1]=="Draw Two":
        n=(d["turn"]+d["dir"])%len(d["order"])
        for _ in range(2):
            if not d["deck"]: recycle=d["discard"][:-1];random.shuffle(recycle);d["deck"]=recycle;d["discard"]=d["discard"][-1:]
            if d["deck"]: d["hands"][d["order"][n]].append(d["deck"].pop())
        d["turn"]=(n+d["dir"])%len(d["order"])
    else:d["turn"]=(d["turn"]+d["dir"])%len(d["order"])
    await q.answer("✅ Played");await uno_refresh(ctx,cid);await uno_turn(ctx,cid)

def recycle(d):
    if len(d["discard"])>1:
        x=d["discard"][-1];a=d["discard"][:-1];random.shuffle(a);d["deck"]=a;d["discard"]=[x]

async def uno_draw(q,ctx,cid,p):
    if q.from_user.id!=p:return await q.answer("❌ Not your button!",show_alert=True)
    s=S(cid);d=s["d"]
    if ucur(d)!=p:return await q.answer("⏳ Not your turn!",show_alert=True)
    recycle(d)
    if d["deck"]:d["hands"][p].append(d["deck"].pop())
    d["turn"]=(d["turn"]+d["dir"])%len(d["order"])
    await q.answer("🎴 Drawn");await uno_refresh(ctx,cid);await uno_turn(ctx,cid)

async def uno_uno(q,ctx,cid,p):
    if q.from_user.id!=p:return
    s=S(cid);d=s["d"]
    if len(d["hands"][p])==1:
        await q.answer("📢 UNO!");await ctx.bot.send_message(cid,f"📢 {mention(p,d['names'][p])} called <b>UNO!</b>",parse_mode="HTML")
    else:await q.answer("❌ You need one card.",show_alert=True)

async def uno_color(q,ctx,cid,p,col):
    if q.from_user.id!=p:return
    s=S(cid);d=s["d"]
    d["color"]=col;d["turn"]=(d["turn"]+d["dir"])%len(d["order"])
    await q.answer("Colour selected");await uno_refresh(ctx,cid);await uno_turn(ctx,cid)

# ---------------- WORD ----------------

WORDS={"MANGO":"🥭 Tropical fruit","TIGER":"🐅 Big striped cat","OCEAN":"🌊 Salt water","ROCKET":"🚀 Goes to space",
       "CHESS":"♟️ Board game","PYTHON":"🐍 Snake / programming language","MUSIC":"🎵 Melody and rhythm"}

async def word_launch(ctx,cid):
    s=S(cid);d=s["d"];d["phase"]="live";d["word"]=random.choice(list(WORDS))
    await ctx.bot.send_message(cid,f"🔤 <b>WORD GAME STARTED!</b>\n\n💡 Clue: <b>{WORDS[d['word']]}</b>\n\nUse <code>/guess WORD</code>",parse_mode="HTML")

async def guess(u,c):
    if u.effective_chat.type=="private":return
    s=S(u.effective_chat.id)
    if s["game"]!="word" or s["d"].get("phase")!="live":return
    if not c.args:return await u.message.reply_text("Use /guess WORD")
    if c.args[0].upper()==s["d"]["word"]:
        await u.message.reply_text(f"🏆 <b>CORRECT!</b>\nAnswer: <b>{s['d']['word']}</b>",parse_mode="HTML");reset(u.effective_chat.id)
    else:await u.message.reply_text("❌ Wrong! Try again.")

# ---------------- CRICKET ----------------

async def cricket_launch(ctx,cid):
    s=S(cid);a,b=s["players"][:2];s["d"]={"phase":"live","bat":a["id"],"bowl":b["id"],"score":0,"wickets":0,"balls":0,"inn":1,"target":None,"pending":{}}
    await cricket_status(ctx,cid)

async def cricket_status(ctx,cid):
    s=S(cid);d=s["d"]
    bn=next(p["name"] for p in s["players"] if p["id"]==d["bat"])
    wn=next(p["name"] for p in s["players"] if p["id"]==d["bowl"])
    await ctx.bot.send_message(cid,f"🏏 <b>CRICKET</b>\n\n🏏 Bat: {mention(d['bat'],bn)}\n🎯 Bowl: {mention(d['bowl'],wn)}\n📊 <b>{d['score']}/{d['wickets']}</b>\n⏱️ Ball {d['balls']}/36\n\n/bat 0-6  •  /bowl 0-6",parse_mode="HTML")

async def cricket_num(u,c,batting):
    if u.effective_chat.type=="private":return
    s=S(u.effective_chat.id)
    if s["game"]!="cricket":return
    d=s["d"];pid=u.effective_user.id
    role=d["bat"] if batting else d["bowl"]
    if pid!=role:return await u.message.reply_text("⏳ Not your turn.")
    try:n=int(c.args[0])
    except:return await u.message.reply_text("Use 0–6.")
    if n<0 or n>6:return await u.message.reply_text("Use 0–6.")
    d["pending"][pid]=n
    if d["bat"] not in d["pending"] or d["bowl"] not in d["pending"]:
        return await u.message.reply_text(f"✅ Locked <b>{n}</b>",parse_mode="HTML")
    b=d["pending"].pop(d["bat"]);w=d["pending"].pop(d["bowl"]);d["balls"]+=1
    if b==w:d["wickets"]+=1;msg=f"💥 <b>WICKET!</b> Both chose {b}"
    else:d["score"]+=b;msg=f"🏏 {b} vs {w} → <b>+{b} runs</b>"
    await u.message.reply_text(f"{msg}\n📊 {d['score']}/{d['wickets']}",parse_mode="HTML")
    if d["target"] and d["score"]>=d["target"]:
        await u.message.reply_text("🏆 <b>CHASE COMPLETE!</b>",parse_mode="HTML");reset(u.effective_chat.id);return
    if d["balls"]>=36 or d["wickets"]>=7:
        if d["inn"]==1:
            target=d["score"]+1;bat,bowl=d["bowl"],d["bat"]
            d.update({"inn":2,"target":target,"score":0,"wickets":0,"balls":0,"bat":bat,"bowl":bowl,"pending":{}})
            await u.message.reply_text(f"🔄 <b>INNINGS BREAK</b>\n🎯 Target: <b>{target}</b>",parse_mode="HTML")
            await cricket_status(c,u.effective_chat.id)
        else:
            await u.message.reply_text("🏆 <b>MATCH OVER!</b>",parse_mode="HTML");reset(u.effective_chat.id)
    else:await cricket_status(c,u.effective_chat.id)

async def bat(u,c):await cricket_num(u,c,True)
async def bowl(u,c):await cricket_num(u,c,False)

# ---------------- LUDO ----------------

async def ludo_launch(ctx,cid):
    s=S(cid);s["d"]={"phase":"mode"}
    await ctx.bot.send_message(cid,"🎲 <b>CHOOSE LUDO MODE</b>",parse_mode="HTML",
      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎲 NORMAL",callback_data=f"l:m:{cid}:normal"),
                                           InlineKeyboardButton("🔥 CHAOS",callback_data=f"l:m:{cid}:chaos")]]))

async def ludo_mode(q,ctx,cid,mode):
    s=S(cid);ids=[p["id"] for p in s["players"]]
    s["d"]={"phase":"live","mode":mode,"turn":0,"pos":{p:0 for p in ids}}
    p=ids[0];await q.answer()
    await ctx.bot.send_message(cid,f"🎲 <b>{mode.upper()} LUDO STARTED!</b>\n\n🎯 {mention(p,next(x['name'] for x in s['players'] if x['id']==p))}",
      parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎲 ROLL",callback_data=f"l:r:{cid}:{p}")]]))

async def ludo_roll(q,ctx,cid,p):
    if q.from_user.id!=p:return await q.answer("❌ Not your turn!",show_alert=True)
    s=S(cid);d=s["d"];ids=[x["id"] for x in s["players"]]
    if ids[d["turn"]]!=p:return await q.answer("⏳ Not your turn!",show_alert=True)
    r=random.randint(1,6);d["pos"][p]+=r;bonus=d["mode"]=="chaos" and r==6
    if d["pos"][p]>=30:
        await ctx.bot.send_message(cid,f"🏆 <b>LUDO WINNER!</b>\n👑 {mention(p,next(x['name'] for x in s['players'] if x['id']==p))}",parse_mode="HTML");reset(cid);return
    if not bonus:d["turn"]=(d["turn"]+1)%len(ids)
    n=ids[d["turn"]]
    await q.answer(f"🎲 {r}")
    await ctx.bot.send_message(cid,f"🎲 {mention(p,next(x['name'] for x in s['players'] if x['id']==p))} rolled <b>{r}</b>\n📍 {d['pos'][p]}\n🎯 Next: {mention(n,next(x['name'] for x in s['players'] if x['id']==n))}",
      parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎲 ROLL",callback_data=f"l:r:{cid}:{n}")]]))

# ---------------- END / STICKERS ----------------

async def end(u,c):
    if u.effective_chat.type=="private":return
    cid=u.effective_chat.id;s=S(cid)
    if not s["game"]:return await u.message.reply_text("❌ No active match.")
    reset(cid);await u.message.reply_text("🛑 <b>MATCH ENDED</b>\n✅ Ready for a new game.",parse_mode="HTML")

async def stickerid(u,c):
    r=u.message.reply_to_message
    if not r or not r.sticker:return await u.message.reply_text("Reply to a sticker with /stickerid")
    await u.message.reply_text(f"<code>{r.sticker.file_id}</code>",parse_mode="HTML")

async def savecard(u,c):
    r=u.message.reply_to_message
    if not r or not r.sticker or not c.args:return await u.message.reply_text("Reply to sticker: /savecard RED_8")
    STICKERS["_".join(c.args).upper()]=r.sticker.file_id
    await u.message.reply_text("✅ Sticker saved.")

async def stickers(u,c):
    await u.message.reply_text("🃏 Saved: "+(", ".join(sorted(STICKERS)) if STICKERS else "none"))

# ---------------- CALLBACKS ----------------

async def cb(u,c):
    q=u.callback_query;data=q.data;await q.answer()
    if data.startswith("m:"):
        g=data.split(":")[1]
        if g=="lb":
            await q.message.reply_text("🏆 Leaderboard is enabled in the bot.",parse_mode="HTML");return
        await begin_from_button(q,c,g);return
    if data.startswith("join:"):await join(q,c,data.split(":")[1]);return
    if data.startswith("force:"):await force(q,c,data.split(":")[1]);return
    if data.startswith("leave:"):await leave(q,c,data.split(":")[1]);return
    p=data.split(":")
    if data.startswith("u:p:"):await uno_play(q,c,int(p[2]),int(p[3]),int(p[4]))
    elif data.startswith("u:d:"):await uno_draw(q,c,int(p[2]),int(p[3]))
    elif data.startswith("u:n:"):await uno_uno(q,c,int(p[2]),int(p[3]))
    elif data.startswith("u:c:"):await uno_color(q,c,int(p[2]),int(p[3]),p[4])
    elif data.startswith("l:m:"):await ludo_mode(q,c,int(p[2]),p[3])
    elif data.startswith("l:r:"):await ludo_roll(q,c,int(p[2]),int(p[3]))

async def begin_from_button(q,c,g):
    cid=q.message.chat.id;s=S(cid)
    if s["game"]:return await q.answer("🔒 Match already running.",show_alert=True)
    s["game"]=g;s["host"]=q.from_user.id;s["players"]= [{"id":q.from_user.id,"name":q.from_user.full_name}];s["d"]={"phase":"join"}
    await q.message.reply_text(f"🎮 <b>{g.upper()} LOBBY</b>\n\n👥 Max {MAX}\n⏱️ {JOIN_TIME}s",parse_mode="HTML",reply_markup=lobby(g))
    s["task"]=asyncio.create_task(auto(c,cid,g))

async def join(q,c,g):
    cid=q.message.chat.id;s=S(cid)
    if s["game"]!=g:return
    if any(x["id"]==q.from_user.id for x in s["players"]):return await q.answer("Already joined!",show_alert=True)
    if len(s["players"])>=MAX:return await q.answer("Lobby full!",show_alert=True)
    s["players"].append({"id":q.from_user.id,"name":q.from_user.full_name})
    await q.message.reply_text(f"🟢 {mention(q.from_user.id,q.from_user.full_name)} joined!\n👥 {len(s['players'])}/{MAX}",parse_mode="HTML")

async def force(q,c,g):
    s=S(q.message.chat.id)
    if len(s["players"])<2:return await q.answer("Minimum 2 players.",show_alert=True)
    await launch(c,q.message.chat.id,g)

async def leave(q,c,g):
    s=S(q.message.chat.id);s["players"]=[p for p in s["players"] if p["id"]!=q.from_user.id]
    await q.answer("🚪 Left.")

# ---------------- COMMANDS ----------------

async def uno(u,c):await begin(u,c,"uno")
async def word(u,c):await begin(u,c,"word")
async def cricket(u,c):await begin(u,c,"cricket")
async def ludo(u,c):await begin(u,c,"ludo")

def main():
    app=Application.builder().token(TOKEN).build()
    for cmd,fn in [("start",start),("menu",menu_cmd),("uno",uno),("word",word),("cricket",cricket),
                   ("ludo",ludo),("guess",guess),("bat",bat),("bowl",bowl),("end",end),
                   ("stickerid",stickerid),("savecard",savecard),("stickerlist",stickers)]:
        app.add_handler(CommandHandler(cmd,fn))
    app.add_handler(CallbackQueryHandler(cb))
    print("🤖 CC Gaming Bot Started")
    app.run_polling()

if __name__=="__main__":
    main()
