"""Imagens do combate: mapa e painel.

Estética: fantasia sombria com toques de cartoon. Fundo escuro, cores fortes por Party,
fichas redondas com anel grosso, cartões de cantos arredondados e emblemas das organizações.
Fontes: Poppins Bold (nomes e números), Poppins Medium (rótulos), Lora Italic ("família · raça").
Tudo é desenhado em dobro de resolução e reduzido no fim, para ficar com bordas suaves.
"""
from __future__ import annotations
import io
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

K = 2                                   # fator de supersampling
COLS, ROWS = 13, 9
CELL, GAP, MARGEM, CALCADA = 70, 4, 16, 26

# ---------------------------------------------------------------- cores
TEXTO = (244, 241, 235)
APAGADO = (156, 152, 170)
PAINEL_BG = (17, 18, 26)
CARTAO = (31, 33, 46)
OURO = (255, 214, 60)
SANGUE = (214, 36, 52)                  # inimigos e NPCs (fora das Parties)
PARTY_CORES = [(255, 122, 41), (35, 214, 196), (255, 64, 160), (255, 200, 40), (60, 160, 255),
               (160, 230, 60), (176, 110, 255), (240, 240, 240), (255, 150, 150), (200, 160, 110)]
VIDA_OK, VIDA_MEIO, VIDA_BAIXA = (84, 214, 104), (255, 190, 50), (255, 70, 80)
EFEITO_COR = {"queimadura": (255, 111, 48), "sangramento": (214, 40, 70), "lentidao": (64, 170, 230),
              "preso": (88, 185, 84), "hipnotizado": (168, 120, 230), "atordoado": (232, 200, 60),
              "determinacao": (255, 214, 60), "barreira": (70, 150, 255)}
EXTRA_COR = (74, 66, 112)               # técnicas e transformações ligadas
FAIXA_CARTOLA = {0: None, 1: (255, 208, 40), 2: (60, 140, 255), 3: (230, 50, 60)}
ORG_NOME = {"billy_spaces": "Billy Spaces", "cartolas": "Cartolas"}

LOCAIS = {   # fundos do mapa; o narrador troca com /combate local
    "billy_landia": {"nome": "Billy Landia", "bg": (33, 39, 49), "motivo": "engrenagem"},
    "snow_landia": {"nome": "Snow Landia", "bg": (22, 32, 56), "motivo": None},
    "plan_landia": {"nome": "Plan Landia", "bg": (22, 44, 33), "motivo": None},
}

PASTA = Path(__file__).parent
_CACHE: dict = {}


# ---------------------------------------------------------------- utilidades
def S(v: float) -> int:
    return int(round(v * K))


def fonte(estilo: str, tam: float):
    arq = {"bold": "Poppins-Bold.ttf", "medio": "Poppins-Medium.ttf", "lora": "Lora-Italic-Variable.ttf"}[estilo]
    chave = (arq, tam)
    if chave not in _CACHE:
        try:
            f = ImageFont.truetype(str(PASTA / arq), S(tam))
            if estilo == "lora":
                try:
                    f.set_variation_by_axes([600])
                except Exception:
                    pass
        except OSError:
            f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", S(tam))
        _CACHE[chave] = f
    return _CACHE[chave]


def largura(d, txt, f) -> float:
    return d.textlength(txt, font=f) / K


def tx(d, x, y, txt, f, cor, ancora="la"):
    d.text((S(x), S(y)), txt, font=f, fill=cor, anchor=ancora)


def rr(d, box, r, fill=None, outline=None, w=0):
    d.rounded_rectangle([S(v) for v in box], radius=S(r), fill=fill, outline=outline, width=S(w) if w else 0)


def oval(d, cx, cy, r, fill=None, outline=None, w=0):
    d.ellipse([S(cx - r), S(cy - r), S(cx + r), S(cy + r)], fill=fill, outline=outline, width=S(w) if w else 0)


def misturar(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def escuro(c, t=0.55):
    return misturar(c, (0, 0, 0), t)


def cor_texto_sobre(cor):
    lum = 0.299 * cor[0] + 0.587 * cor[1] + 0.114 * cor[2]
    return (24, 22, 30) if lum > 150 else (255, 255, 255)


def nome_casa(pos) -> str:
    col, lin = pos
    return f"{chr(65 + lin)}{col + 1}"


def iniciais(nome: str) -> str:
    partes = [p for p in nome.replace("—", " ").split() if p[0].isalpha()]
    if len(partes) >= 2:
        return (partes[0][0] + partes[1][0]).upper()
    return nome[:2].upper()


def para_bytes(img: Image.Image) -> io.BytesIO:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    buf.seek(0)
    return buf


def cor_party(c):
    if c.equipe == "B":
        return SANGUE
    return PARTY_CORES[c.party_n % len(PARTY_CORES)]


def cor_vida(frac):
    return VIDA_OK if frac > .5 else VIDA_MEIO if frac > .25 else VIDA_BAIXA


def _final(img):
    return img.resize((img.width // K, img.height // K), Image.LANCZOS)


# ---------------------------------------------------------------- emblemas e avatares
def emblema(d, cx, cy, r, org, rank=0):
    """Selo redondo: escudo (Billy Spaces) ou cartola com listra de rank (Cartolas)."""
    if org not in ORG_NOME:
        return
    oval(d, cx, cy, r + 1.5, fill=(10, 10, 14))
    oval(d, cx, cy, r, fill=(238, 233, 222))
    if org == "billy_spaces":
        pts = [(-.48, -.52), (.48, -.52), (.48, .12), (0, .66), (-.48, .12)]
        d.polygon([(S(cx + x * r), S(cy + y * r)) for x, y in pts], fill=(40, 96, 224))
        d.polygon([(S(cx + x * r * .5), S(cy + y * r * .5 - r * .05)) for x, y in pts], fill=(238, 233, 222))
        d.polygon([(S(cx + x * r * .3), S(cy + y * r * .3 - r * .02)) for x, y in pts], fill=(40, 96, 224))
    else:
        negro = (18, 15, 20)
        rr(d, (cx - r * .66, cy + r * .22, cx + r * .66, cy + r * .42), r * .08, fill=negro)       # aba
        rr(d, (cx - r * .40, cy - r * .58, cx + r * .40, cy + r * .30), r * .10, fill=negro)      # copa
        faixa = FAIXA_CARTOLA.get(rank, None) or (90, 84, 100)
        d.rectangle([S(cx - r * .40), S(cy + r * .02), S(cx + r * .40), S(cy + r * .20)], fill=faixa)


def _hat_silhouette(d, cx, top, w, cor, faixa):
    rr(d, (cx - w * .75, top + w * .55, cx + w * .75, top + w * .75), w * .08, fill=cor)
    rr(d, (cx - w * .46, top - w * .45, cx + w * .46, top + w * .62), w * .10, fill=cor)
    d.rectangle([S(cx - w * .46), S(top + w * .28), S(cx + w * .46), S(top + w * .47)], fill=faixa or (80, 70, 90))


def avatar_img(c, diam: float) -> Image.Image:
    """Imagem quadrada do personagem: /aparencia, ou silhueta (NPC), ou iniciais (jogador sem aparência)."""
    n = S(diam)
    if c.avatar is not None:
        im = ImageOps.fit(c.avatar.convert("RGB"), (n, n), Image.LANCZOS)
    else:
        npc = c.equipe == "B" or not c.dono_id
        fundo = (70, 22, 32) if npc else escuro(cor_party(c), 0.62)
        im = Image.new("RGB", (n, n), fundo)
        d = ImageDraw.Draw(im)
        sil = (22, 14, 20) if npc else misturar(fundo, (0, 0, 0), .35)
        if npc:
            cx, cy = n / 2 / K, n / 2 / K
            u = diam
            oval(d, cx, cy + u * .02, u * .17, fill=sil)                                  # cabeça
            d.ellipse([S(cx - u * .38), S(cy + u * .22), S(cx + u * .38), S(cy + u * .80)], fill=sil)   # ombros
            if c.org == "cartolas":
                _hat_silhouette(d, cx, cy - u * .36, u * .34, sil, FAIXA_CARTOLA.get(c.org_rank))
        else:
            tx(d, diam / 2, diam / 2, iniciais(c.nome), fonte("bold", diam * .38), TEXTO, "mm")
    if not c.vivo:
        im = ImageEnhance.Brightness(ImageOps.grayscale(im).convert("RGB")).enhance(.5)
    return im


def colar_redondo(img, im, cx, cy, diam):
    n = S(diam)
    mask = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, n - 1, n - 1], fill=255)
    img.paste(im, (S(cx) - n // 2, S(cy) - n // 2), mask)


def ficha_redonda(img, d, cx, cy, R, c, ativo=False, anel=5.0):
    """Avatar com anel grosso na cor da Party (cinza se caiu)."""
    cor = cor_party(c) if c.vivo else (90, 90, 100)
    if ativo:
        oval(d, cx, cy, R + 7, outline=OURO, w=3)
    oval(d, cx, cy + 2.5, R, fill=(8, 9, 12))                                # sombra de desenho animado
    oval(d, cx, cy, R, fill=cor)
    oval(d, cx, cy, R - anel, fill=(20, 22, 30))
    colar_redondo(img, avatar_img(c, 2 * (R - anel)), cx, cy, 2 * (R - anel))
    if not c.vivo:
        for s in (-1, 1):
            d.line([S(cx - R * .45), S(cy - R * .45 * s), S(cx + R * .45), S(cy + R * .45 * s)],
                   fill=(255, 90, 100), width=S(4))


def barra_vida(d, x, y, w, h, frac, fundo=(10, 11, 15)):
    rr(d, (x, y, x + w, y + h), h / 2, fill=fundo)
    if frac > 0:
        rr(d, (x + 1, y + 1, x + 1 + max(h - 2, (w - 2) * frac), y + h - 1), (h - 2) / 2, fill=cor_vida(frac))


# ---------------------------------------------------------------- motivos de fundo
def _engrenagem(d, cx, cy, R, cor, dentes=14):
    for i in range(dentes):
        a = 2 * math.pi * i / dentes
        ux, uy = math.cos(a), math.sin(a)
        px, py = -uy, ux
        w1, w2 = R * .13, R * .09
        pts = [(cx + ux * R * .86 + px * w1, cy + uy * R * .86 + py * w1),
               (cx + ux * R * 1.12 + px * w2, cy + uy * R * 1.12 + py * w2),
               (cx + ux * R * 1.12 - px * w2, cy + uy * R * 1.12 - py * w2),
               (cx + ux * R * .86 - px * w1, cy + uy * R * .86 - py * w1)]
        d.polygon([(S(x), S(y)) for x, y in pts], fill=cor)
    oval(d, cx, cy, R, fill=cor)


# ---------------------------------------------------------------- mapa
def desenhar_mapa(combatentes, destaque=None, local="billy_landia", coords=True) -> Image.Image:
    info = LOCAIS.get(local, LOCAIS["billy_landia"])
    bg = info["bg"]
    gut_x = CALCADA if coords else 0
    w = MARGEM + gut_x + COLS * CELL + (COLS - 1) * GAP + MARGEM
    h = MARGEM + gut_x + ROWS * CELL + (ROWS - 1) * GAP + MARGEM
    img = Image.new("RGB", (S(w), S(h)), bg)
    d = ImageDraw.Draw(img)
    x0, y0 = MARGEM + gut_x, MARGEM + gut_x

    if info["motivo"] == "engrenagem":
        cx, cy = x0 + (COLS * CELL + (COLS - 1) * GAP) / 2, y0 + (ROWS * CELL + (ROWS - 1) * GAP) / 2
        claro = misturar(bg, (255, 255, 255), .07)
        _engrenagem(d, cx, cy, 250, claro)
        oval(d, cx, cy, 160, fill=bg)
        _engrenagem(d, cx, cy, 80, claro, dentes=8)
        oval(d, cx, cy, 34, fill=bg)

    def origem(col, lin):
        return x0 + col * (CELL + GAP), y0 + lin * (CELL + GAP)

    ladrilho = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dl = ImageDraw.Draw(ladrilho)
    for lin in range(ROWS):
        for col in range(COLS):
            x, y = origem(col, lin)
            cor = (255, 255, 255, 16)
            if destaque is not None and tuple(destaque.pos) == (col, lin):
                cor = (255, 214, 60, 70)
            dl.rounded_rectangle([S(x), S(y), S(x + CELL), S(y + CELL)], radius=S(9), fill=cor)
    img = Image.alpha_composite(img.convert("RGBA"), ladrilho).convert("RGB")
    d = ImageDraw.Draw(img)

    if coords:
        f = fonte("medio", 13)
        for col in range(COLS):
            x, _ = origem(col, 0)
            tx(d, x + CELL / 2, MARGEM + gut_x / 2, str(col + 1), f, APAGADO, "mm")
        for lin in range(ROWS):
            _, y = origem(0, lin)
            tx(d, MARGEM + gut_x / 2, y + CELL / 2, chr(65 + lin), f, APAGADO, "mm")

    por_casa: dict = {}
    for c in combatentes:
        por_casa.setdefault(tuple(c.pos), []).append(c)
    for (col, lin), grupo in por_casa.items():
        x, y = origem(col, lin)
        cx, cy = x + CELL / 2, y + CELL / 2
        if len(grupo) == 1:
            _token(img, d, cx, cy - 4, grupo[0], destaque is grupo[0])
        else:
            for c, (ox, oy) in zip(grupo[:4], [(-16, -16), (16, -16), (-16, 16), (16, 16)]):
                _token_mini(img, d, cx + ox, cy + oy, c, destaque is c)
    return _final(img)


def _token(img, d, cx, cy, c, ativo):
    R = 28
    ficha_redonda(img, d, cx, cy, R, c, ativo, anel=5.5)
    barra_vida(d, cx - 23, cy + R + 3, 46, 7, max(0, c.hp / c.hp_max) if c.vivo else 0)
    if c.org in ORG_NOME and c.vivo:
        emblema(d, cx - R + 3, cy - R + 4, 10, c.org, c.org_rank)
    for i, e in enumerate(c.efeitos[:3]):
        oval(d, cx + R + 1, cy - R + 8 + i * 13, 6.5, fill=(10, 10, 14))
        oval(d, cx + R + 1, cy - R + 8 + i * 13, 5, fill=EFEITO_COR.get(e["id"], APAGADO))


def _token_mini(img, d, cx, cy, c, ativo):
    R = 15
    ficha_redonda(img, d, cx, cy, R, c, ativo, anel=3.5)
    barra_vida(d, cx - 13, cy + R + 2, 26, 4, max(0, c.hp / c.hp_max) if c.vivo else 0)


# ---------------------------------------------------------------- painel
def _tag(d, x, y, h, txt, f, fill, fg=None, ate=None):
    fg = fg or cor_texto_sobre(fill)
    w = largura(d, txt, f) + h * .85
    if ate is not None and x + w > ate:
        return None
    rr(d, (x, y, x + w, y + h), h / 2, fill=fill)
    tx(d, x + w / 2, y + h / 2 + .5, txt, f, fg, "mm")
    return w


def _chapeu_icone(d, cx, cy, s):
    negro = (236, 232, 222)
    rr(d, (cx - s * .62, cy + s * .22, cx + s * .62, cy + s * .42), s * .08, fill=negro)
    rr(d, (cx - s * .38, cy - s * .62, cx + s * .38, cy + s * .30), s * .10, fill=negro)
    d.rectangle([S(cx - s * .38), S(cy + s * .02), S(cx + s * .38), S(cy + s * .20)], fill=(214, 36, 52))


def _ativos(c):
    """Lista (texto, cor) do que está ativo: efeitos com turnos e técnicas/transformações ligadas."""
    from engine import EFEITOS
    itens = []
    for e in c.efeitos:
        itens.append((f"{EFEITOS[e['id']]['nome']} {e['turnos']}t", EFEITO_COR.get(e["id"], APAGADO)))
    for t in c.ativos_extra:
        itens.append((t, EXTRA_COR))
    return itens


def desenhar_painel(combatentes, titulo="Combate", subtitulo="", ativo=None, local="billy_landia") -> Image.Image:
    n = len(combatentes)
    compacto = n > 5
    W, m, vao = 900, 14, 10
    cab_h = 92
    u = .78 if compacto else 1.0
    card_h = round(150 * u)
    cols = 2 if compacto else 1
    card_w = (W - 2 * m - (cols - 1) * vao) // cols
    linhas = math.ceil(n / cols)
    H = m + cab_h + vao + linhas * card_h + (linhas - 1) * vao + m
    img = Image.new("RGB", (S(W), S(H)), PAINEL_BG)
    d = ImageDraw.Draw(img)

    # cabeçalho
    rr(d, (m, m, W - m, m + cab_h), 20, fill=(24, 22, 34))
    _chapeu_icone(d, m + 54, m + cab_h / 2 + 2, 50)
    tx(d, m + 104, m + 12, titulo, fonte("bold", 38), TEXTO)
    if subtitulo:
        tx(d, m + 106, m + 58, subtitulo, fonte("lora", 23), (206, 200, 222))
    nome_local = LOCAIS.get(local, LOCAIS["billy_landia"])["nome"]
    f_l = fonte("medio", 17)
    wl = largura(d, nome_local, f_l) + 30
    rr(d, (W - m - 22 - wl, m + cab_h / 2 - 17, W - m - 22, m + cab_h / 2 + 17), 17, fill=(40, 38, 58))
    tx(d, W - m - 22 - wl / 2, m + cab_h / 2 + .5, nome_local, f_l, APAGADO, "mm")

    for i, c in enumerate(combatentes):
        x = m + (i % cols) * (card_w + vao)
        y = m + cab_h + vao + (i // cols) * (card_h + vao)
        _cartao(img, d, c, x, y, card_w, card_h, u, ativo is c, compacto)
    return _final(img)


def recortar(d, txt, f, maxw):
    if largura(d, txt, f) <= maxw:
        return txt
    while txt and largura(d, txt + "…", f) > maxw:
        txt = txt[:-1]
    return txt.rstrip() + "…"


def _pips_mana(d, c, dir_, py, raio, passo, f_txt):
    if not (c.mana_max and c.vivo):
        return
    if c.mana_max <= 10:
        for k in range(c.mana_max):
            oval(d, dir_ - raio - k * passo, py, raio, fill=(86, 160, 255) if k < c.mana_turnos else (46, 52, 74))
    else:
        tx(d, dir_, py, f"mana {c.mana_turnos}/{c.mana_max}", f_txt, APAGADO, "rm")


def _cartao(img, d, c, x, y, w, h, u, vez, compacto):
    cor = cor_party(c) if c.vivo else (90, 90, 100)
    fundo = misturar(CARTAO, cor, .22) if vez else CARTAO
    rr(d, (x, y, x + w, y + h), 20 * u, fill=cor)
    rr(d, (x + 10 * u, y, x + w, y + h), 20 * u, fill=fundo)
    d.rectangle([S(x + 10 * u), S(y + 4 * u), S(x + 30 * u), S(y + h - 4 * u)], fill=fundo)
    if vez:
        rr(d, (x + 1, y + 1, x + w - 1, y + h - 1), 20 * u, outline=cor, w=3)

    R = (40 if compacto else 50)
    ax, ay = x + (22 if compacto else 28) + R, y + h / 2
    ficha_redonda(img, d, ax, ay, R, c, False, anel=4.5 if compacto else 5)
    d = ImageDraw.Draw(img)

    esq = ax + R + (14 if compacto else 18)
    dir_ = x + w - (18 if compacto else 24)
    vivo = c.vivo
    tinta = TEXTO if vivo else (150, 148, 160)
    suave = (206, 200, 222) if vivo else (130, 128, 142)
    emb = 2 * (11 if compacto else 14) + 8 if c.org in ORG_NOME else 0

    if compacto:
        f_nome, f_lora, f_tag = fonte("bold", 22), fonte("lora", 17), fonte("medio", 12.5)
        pill_vez = (largura(d, "VEZ", fonte("bold", 12)) + 20 + 6) if vez and vivo else 0
        nome = recortar(d, c.nome, f_nome, dir_ - esq - emb - pill_vez)
        ny = y + 12
        tx(d, esq, ny, nome, f_nome, tinta)
        if emb:
            emblema(d, esq + largura(d, nome, f_nome) + 8 + 11, ny + 16, 11, c.org, c.org_rank)
        linha = " · ".join(p for p in (c.familia, c.raca) if p) or "—"
        tx(d, esq, y + 44, linha, f_lora, suave)
        # vida (embaixo, direita)
        f_v, f_t = fonte("bold", 31), fonte("medio", 16)
        total = f"/{round(c.hp_max)}"
        wt = largura(d, total, f_t)
        tx(d, dir_, y + 88, total, f_t, APAGADO, "rs")
        tx(d, dir_ - wt - 2, y + 88, f"{round(c.hp)}", f_v, tinta, "rs")
        bw = 132
        barra_vida(d, dir_ - bw, y + 96, bw, 12, max(0, c.hp / c.hp_max) if vivo else 0)
        if vivo:
            _pips_mana(d, c, dir_, y + 56, 4.5, 12.5, fonte("medio", 12.5))
        else:
            tx(d, dir_, y + 56, "Caiu", fonte("bold", 14), (255, 90, 100), "rm")
        ty, th, limite = y + h - 32, 22, dir_ - bw - 14
        gap = 5
    else:
        f_nome, f_lora, f_tag = fonte("bold", 30), fonte("lora", 22), fonte("medio", 14.5)
        pill_vez = (largura(d, "VEZ", fonte("bold", 15)) + 22) if vez and vivo else 0
        nome = recortar(d, c.nome, f_nome, dir_ - esq - emb - 190)
        ny = y + 16
        tx(d, esq, ny, nome, f_nome, tinta)
        if emb:
            emblema(d, esq + largura(d, nome, f_nome) + 8 + 14, ny + 21, 14, c.org, c.org_rank)
        linha = " · ".join(p for p in (c.familia, c.raca) if p) or "—"
        tx(d, esq, y + 58, linha, f_lora, suave)
        f_v, f_t = fonte("bold", 46), fonte("medio", 20)
        total = f"/{round(c.hp_max)}"
        wt = largura(d, total, f_t)
        tx(d, dir_, y + 70, total, f_t, APAGADO, "rs")
        tx(d, dir_ - wt - 2, y + 70, f"{round(c.hp)}", f_v, tinta, "rs")
        bw = 172
        barra_vida(d, dir_ - bw, y + 82, bw, 16, max(0, c.hp / c.hp_max) if vivo else 0)
        if vivo:
            _pips_mana(d, c, dir_, y + h - 21, 6, 17, fonte("medio", 15))
        else:
            tx(d, dir_, y + h - 21, "Caiu", fonte("bold", 17), (255, 90, 100), "rm")
        ty, th, limite = y + h - 42, 26, dir_ - bw - 16
        gap = 6

    # etiquetas: Party (só no cartão grande) e o que está ativo
    cx_ = esq
    if c.party and not compacto:
        wp = _tag(d, cx_, ty, th, c.party, f_tag, misturar(cor, (0, 0, 0), .15), cor_texto_sobre(cor))
        cx_ += wp + gap
    ativos = _ativos(c) if vivo else []
    mostrados = 0
    for txt, cor_t in ativos:
        wt_ = _tag(d, cx_, ty, th, txt, f_tag, cor_t, ate=limite - (30 if len(ativos) - mostrados > 1 else 0))
        if wt_ is None:
            break
        cx_ += wt_ + gap
        mostrados += 1
    resto = len(ativos) - mostrados
    if resto > 0:
        _tag(d, cx_, ty, th, f"+{resto}", f_tag, (60, 58, 80), TEXTO)
    if vez and vivo:
        fv = fonte("bold", 12 if compacto else 15)
        wv = largura(d, "VEZ", fv) + (20 if compacto else 22)
        hv = 22 if compacto else 24
        y0 = y + (10 if compacto else 8)
        rr(d, (dir_ - wv, y0, dir_, y0 + hv), hv / 2, fill=OURO)
        tx(d, dir_ - wv / 2, y0 + hv / 2 + .5, "VEZ", fv, (30, 24, 8), "mm")
