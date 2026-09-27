"""Gera a imagem 16:9 que o bot exibe na chamada com o aviso de gravação (LGPD)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
BG, FG, ACCENT, MUTED = (17, 24, 39), (255, 255, 255), (239, 68, 68), (203, 213, 225)
F = "/usr/share/fonts/truetype/dejavu/DejaVuSans"

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)
big = ImageFont.truetype(F + "-Bold.ttf", 64)
mid = ImageFont.truetype(F + "-Bold.ttf", 38)
small = ImageFont.truetype(F + ".ttf", 30)

d.ellipse((90, 110, 140, 160), fill=ACCENT)
d.text((165, 100), "GRAVANDO", font=big, fill=ACCENT)
d.text((90, 210), "Esta entrevista está sendo gravada", font=mid, fill=FG)
d.text((90, 262), "e transcrita pela Rubrica.", font=mid, fill=FG)
lines = [
    "• Uso exclusivo da empresa no processo seletivo (LGPD).",
    "• O áudio/vídeo bruto é apagado após a transcrição.",
    "• Você pode pedir a exclusão dos seus dados a qualquer momento.",
    "• Se não concordar, avise o(a) entrevistador(a) agora.",
]
for n, t in enumerate(lines):
    d.text((90, 360 + n * 52), t, font=small, fill=MUTED)
d.text((90, 640), "Rubrica · entrevistas estruturadas", font=small, fill=(148, 163, 184))

out = Path(__file__).resolve().parent.parent / "app" / "assets" / "aviso-lgpd.jpg"
img.save(out, "JPEG", quality=85)
print("ok", out, out.stat().st_size)
