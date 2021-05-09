import asyncio
import secrets
import random
import os
import io
import re

from PIL import Image, ImageEnhance, ImageOps

from pyrogram import filters
from pyrogram.types import InputMediaPhoto, InputMediaVideo

from bot import alemiBot

from util import batchify
from util.permission import is_allowed, is_superuser
from util.message import edit_or_reply, is_me
from util.text import order_suffix
from util.getters import get_text
from util.command import filterCommand
from util.decorators import report_error, set_offline
from util.help import HelpCategory

import logging
logger = logging.getLogger(__name__)

HELP = HelpCategory("MEME")
INTERRUPT = False

# TODO make this an util and maybe pass **kwargs
async def send_media_appropriately(client, message, fname, reply_to, extra_text=""):
	if fname.endswith((".jpg", ".jpeg", ".png")):
		await client.send_chat_action(message.chat.id, "upload_photo")
		await client.send_photo(message.chat.id, "data/memes/"+fname, reply_to_message_id=reply_to,
								caption=f'` → {extra_text} ` **{fname}**')
	elif fname.endswith((".gif", ".mp4", ".webm")):
		await client.send_chat_action(message.chat.id, "upload_video")
		await client.send_video(message.chat.id, "data/memes/"+fname, reply_to_message_id=reply_to,
								caption=f'` → {extra_text} ` **{fname}**')
	elif fname.endswith((".webp", ".tgs")):
		await client.send_chat_action(message.chat.id, "upload_photo")
		await client.send_sticker(message.chat.id, "data/memes/"+fname, reply_to_message_id=reply_to)
	elif fname.endswith((".mp3", ".ogg", ".wav")):
		await client.send_chat_action(message.chat.id, "upload_audio")
		await client.send_voice(message.chat.id, "data/memes/"+fname, reply_to_message_id=reply_to)
	else:
		await client.send_chat_action(message.chat.id, "upload_document")
		await client.send_document(message.chat.id, "data/memes/"+fname, reply_to_message_id=reply_to,
										caption=f'` → {extra_text} ` **{fname}**')
	await client.send_chat_action(message.chat.id, "cancel")
	

@HELP.add(cmd="[<name>]", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand("meme", list(alemiBot.prefixes), options={
	"batch" : ["-b"]
}, flags=["-list", "-stat", "-stats"]))
@report_error(logger)
@set_offline
async def meme_cmd(client, message):
	"""get a meme from collection

	If a name was specified, get meme matching requested name. Otherwise, get random meme.
	Use flag `-list` to get all meme names and flag `-stats` to get count and disk usage.
	You can send a bunch of random memes together by specifying how many in the `-b` (batch) option \
	(only photos will be sent if a batch is requested).
	Memes can be any filetype.
	"""
	args = message.command
	batch = max(min(int(args["batch"]), 10), 2) if "batch" in args else 0
	reply_to = message.message_id
	if is_me(message) and message.reply_to_message is not None:
		reply_to = message.reply_to_message.message_id
	if "-stat" in args["flags"] or "-stats" in args["flags"]:
		memenumber = len(os.listdir("data/memes"))
		proc_meme = await asyncio.create_subprocess_exec( # ewww this is not cross platform but will do for now
			"du", "-b", "data/memes",
			stdout=asyncio.subprocess.PIPE,
			stderr=asyncio.subprocess.STDOUT)
		stdout, _stderr = await proc_meme.communicate()
		memesize = float(stdout.decode('utf-8').split("\t")[0])
		await edit_or_reply(message, f"` → ` **{memenumber}** memes collected\n`  → ` folder size **{order_suffix(memesize)}**")
	elif "-list" in args["flags"]:
		memes = os.listdir("data/memes")
		memes.sort()
		out = f"` → ` **Meme list** ({len(memes)} total) :\n[ "
		out += ", ".join(memes)
		out += "]"
		await edit_or_reply(message, out)
	elif "cmd" in args and args["cmd"][0] != "-delme":
		name = args["cmd"][0]
		memes = [ s for s in os.listdir("data/memes")
					if s.lower().startswith(name) ]
		if len(memes) > 0:
			fname = memes[0]
			await send_media_appropriately(client, message, fname, reply_to)
		else:
			await edit_or_reply(message, f"`[!] → ` no meme named {args['cmd'][0]}")
	else: 
		if batch > 0:
			memes = []
			while len(memes) < batch:
				fname = secrets.choice(os.listdir("data/memes"))
				if fname.endswith((".jpg", ".jpeg", ".png")):
					await client.send_chat_action(message.chat.id, "upload_photo")
					memes.append(InputMediaPhoto("data/memes/" + fname))
			await client.send_media_group(message.chat.id, memes)
		else:
			fname = secrets.choice(os.listdir("data/memes"))
			await send_media_appropriately(client, message, fname, reply_to, extra_text="Random meme : ")

@HELP.add(cmd="<name>")
@alemiBot.on_message(is_superuser & filterCommand("steal", list(alemiBot.prefixes)))
@report_error(logger)
@set_offline
async def steal_cmd(client, message):
	"""steal a meme

	Save a meme to collection.
	Either attach an image or reply to one.
	A name for the meme must be given (and must not contain spaces)
	"""
	if "cmd" not in message.command:
		return await edit_or_reply(message, "`[!] → ` No meme name provided")
	msg = message
	if message.reply_to_message is not None:
		msg = message.reply_to_message
	if msg.media:
		fpath = await client.download_media(msg, file_name="data/memes/") # + message.command["cmd"][0])
		# await edit_or_reply(message, '` → ` saved meme as {}'.format(fpath))
		path, fname = os.path.splitext(fpath) # this part below is trash, im waiting for my PR on pyrogram
		extension = fname.split(".")
		if len(extension) > 1:
			extension = extension[1]
		else:
			extension = ".jpg" # cmon most memes will be jpg
		newname = message.command["cmd"][0] + '.' + extension
		os.rename(fpath, "data/memes/" + newname)
		await edit_or_reply(message, f'` → ` saved meme as {newname}')
	else:
		await edit_or_reply(message, "`[!] → ` you need to attach or reply to a file, dummy")

#
# This is from https://github.com/Ovyerus/deeppyer
#	I should do some license stuff here but TODO
#

async def fry_image(img: Image) -> Image:
	colours = ( # TODO tweak values
		(random.randint(50, 200), random.randint(40, 170), random.randint(40, 190)),
		(random.randint(190, 255), random.randint(170, 240), random.randint(180, 250))
	)

	img = img.copy().convert("RGB")

	# Crush image to hell and back
	img = img.convert("RGB")
	width, height = img.width, img.height
	img = img.resize((int(width ** random.uniform(0.8, 0.9)), int(height ** random.uniform(0.8, 0.9))), resample=Image.LANCZOS)
	img = img.resize((int(width ** random.uniform(0.85, 0.95)), int(height ** random.uniform(0.85, 0.95))), resample=Image.BILINEAR)
	img = img.resize((int(width ** random.uniform(0.89, 0.98)), int(height ** random.uniform(0.89, 0.98))), resample=Image.BICUBIC)
	img = img.resize((width, height), resample=Image.BICUBIC)
	img = ImageOps.posterize(img, random.randint(3, 7))

	# Generate colour overlay
	overlay = img.split()[0]
	overlay = ImageEnhance.Contrast(overlay).enhance(random.uniform(1.0, 2.0))
	overlay = ImageEnhance.Brightness(overlay).enhance(random.uniform(1.0, 2.0))

	overlay = ImageOps.colorize(overlay, colours[0], colours[1])

	# Overlay red and yellow onto main image and sharpen the hell out of it
	img = Image.blend(img, overlay, random.uniform(0.1, 0.4))
	img = ImageEnhance.Sharpness(img).enhance(random.randint(5, 300))

	return img

@HELP.add(cmd="[-c <n>]", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand("fry", list(alemiBot.prefixes), options={
	"count" : ["-c"]
}))
@report_error(logger)
@set_offline
async def deepfry_cmd(client, message):
	"""deepfry an image

	Will deepfry an image (won't add "laser eyes").
	The number of frying rounds can be specified with `-c`. Will default to 1.
	Code from https://github.com/Ovyerus/deeppyer.
	"""
	args = message.command
	target = message.reply_to_message if message.reply_to_message is not None else message
	if target.media:
		await client.send_chat_action(message.chat.id, "upload_photo")
		msg = await edit_or_reply(message, "` → ` Downloading...")
		count = 1
		if "count" in args:
			count = int(args["count"])
		fpath = await client.download_media(target, file_name="tofry")
		msg.edit(get_text(message) + "\n` → ` Downloading [OK]\n` → ` Frying...")
		image = Image.open(fpath)
	
		for _ in range(count):
			image = await fry_image(image)
		if message.from_user is not None and message.from_user.is_self:
			await msg.edit(get_text(message) +
				"\n` → ` Downloading [OK]\n` → ` Frying [OK]\n` → ` Uploading...")
	
		fried_io = io.BytesIO()
		fried_io.name = "fried.jpg"
		image.save(fried_io, "JPEG")
		fried_io.seek(0)
		await client.send_photo(message.chat.id, fried_io, reply_to_message_id=message.message_id,
									caption=f"` → Fried {count} time{'s' if count > 1 else ''}`")
		if message.from_user is not None and message.from_user.is_self:
			await msg.edit(get_text(message) +
				"\n` → ` Downloading [OK]\n` → ` Frying [OK]\n` → ` Uploading [OK]")
		await client.send_chat_action(message.chat.id, "cancel")
	else:
		await edit_or_reply(message, "`[!] → ` you need to attach or reply to a file, dummy")

#
#	This comes from https://github.com/anuragrana/Python-Scripts/blob/master/image_to_ascii.py
#

def ascii_image(img:Image, new_width:int=120) -> str:
	# resize the image
	width, height = img.size
	aspect_ratio = height/width
	new_height = aspect_ratio * new_width * 0.55
	img = img.resize((new_width, int(new_height)))
	img = img.convert('L')
	
	pixels = img.getdata()
	
	# replace each pixel with a character from array
	chars = ["B","S","#","&","@","$","%","*","!",":","."]
	new_pixels = [chars[pixel//25] for pixel in pixels]
	new_pixels = ''.join(new_pixels)
	
	# split string of chars into multiple strings of length equal to new width and create a list
	new_pixels_count = len(new_pixels)
	ascii_image = [new_pixels[index:index + new_width] for index in range(0, new_pixels_count, new_width)]
	ascii_image = "\n".join(ascii_image)
	return ascii_image

@HELP.add(cmd="[<width>]", sudo=False)
@alemiBot.on_message(is_allowed & filterCommand("ascii", list(alemiBot.prefixes)))
@report_error(logger)
@set_offline
async def ascii_cmd(client, message):
	"""make ascii art of picture

	Roughly convert a picture into ascii art.
	You can specify width of the resulting image in characters as command argument (default is 120).
	If the requested width is lower than 50 characters,	the result will be printed directly into telegram. Else, a txt will be attached.
	Code comes from https://github.com/anuragrana/Python-Scripts/blob/master/image_to_ascii.py.
	"""
	msg = message
	if message.reply_to_message is not None:
		msg = message.reply_to_message
	width = 120
	if "cmd" in message.command:
		width = int(message.command["cmd"][0])
	if msg.media:
		fpath = await client.download_media(msg, file_name="toascii")
		image = Image.open(fpath)

		ascii_result = ascii_image(image, new_width=width)

		if width <= 50:
			await edit_or_reply(message, "``` →\n" + ascii_result + "```")
		else:
			out = io.BytesIO(ascii_result.encode('utf-8'))
			out.name = "ascii.txt"
			await client.send_document(message.chat.id, out, reply_to_message_id=message.message_id,
										caption=f"` → Made ASCII art `")
	else:
		await edit_or_reply(message, "`[!] → ` you need to attach or reply to a file, dummy")

INTERRUPT_PASTA = False

@HELP.add(cmd="<fpath>")
@alemiBot.on_message(is_superuser & filterCommand("pasta", list(alemiBot.prefixes), options={
	"separator" : ["-s", "-sep"],
	"interval" : ["-i", "-intrv"]
}, flags=["-stop", "-mono", "-edit"]))
@report_error(logger)
@set_offline
async def pasta_cmd(client, message):
	"""drop a copypasta

	Give path to a .txt (or any file really) containing long text and bot will drop it in chat.
	Use flag `-stop` to stop ongoing pasta.
	By default,	pasta will be split at newlines (`\n`) and sent at a certain interval (2s), but you can customize both.
	Long messages will still be split in chunks of 4096 characters due to telegram limit.
	Add flag `-mono` to print pasta monospaced.
	Add flag `-edit` to always edit the first message instead of sending new ones.
	Getting a good pasta collection is up to you, make sure to `.r mkdir data/pastas` and `wget` some cool pastas in there!
	"""
	global INTERRUPT_PASTA
	if "-stop" in message.command["flags"]:
		INTERRUPT_PASTA = True
		return
	sep = message.command["separator"] if "separator" in message.command else "\n"
	intrv = float(message.command["interval"]) if "interval" in message.command else 2
	monospace = "-mono" in message.command["flags"]
	edit_this = await client.send_message(message.chat.id, "` → ` Starting") if "-edit" in message.command["flags"] else None
	with open(message.command["cmd"][0], "rb") as f:
		for section in re.split(sep, f.read().decode('utf-8','ignore')):
			for chunk in batchify(section, 4090):
				if chunk.strip() == "":
					continue
				p_mode = None
				if monospace:
					chunk = "```" + chunk + "```"
					p_mode = "markdown"

				if edit_this:
					await edit_this.edit(chunk, parse_mode=p_mode)
				else:
					await client.send_message(message.chat.id, chunk, parse_mode=p_mode)
				await asyncio.sleep(intrv)
				if INTERRUPT_PASTA:
					INTERRUPT_PASTA = False
					raise Exception("Interrupted by user")
	if edit_this:
		await edit_this.edit("` → ` Done")
