"""Bot Discord do RP Billy (esqueleto funcional, ainda não testado no Discord).

Uso:  DISCORD_TOKEN=xxxx python bot.py
Requer: pip install -U discord.py pillow
"""
from __future__ import annotations
import json
import os
import random
from pathlib import Path

import discord
from discord import app_commands

import aparencias
import caminhos
import engine
import render

FICHAS = caminhos.DADOS / "fichas.json"   # {user_id: {nome, equipe, stats, tecnicas, passivas}}
STAFF_ROLE = "Narrador"


def carregar_fichas() -> dict:
    return json.loads(FICHAS.read_text(encoding="utf-8")) if FICHAS.exists() else {}


def salvar_fichas(fichas: dict):
    FICHAS.write_text(json.dumps(fichas, ensure_ascii=False, indent=1), encoding="utf-8")


def combatente_da_ficha(uid: int, ficha: dict, pos) -> engine.Combatente:
    """Monta o combatente a partir da ficha (família, raça, organização, Party e aparência)."""
    return engine.Combatente(
        ficha["nome"], "A", ficha["stats"], ficha["tecnicas"], ficha.get("passivas", []),
        pos=pos, dono_id=uid, familia=ficha.get("familia", ""), raca=ficha.get("raca", ""),
        org=ficha.get("org"), org_rank=ficha.get("org_rank", 0), party=ficha.get("party"),
        avatar=aparencias.imagem_de(ficha.get("aparencia_id")), ativos_extra=list(ficha.get("ativos", [])))


def casa_livre(jogo, col: int, lin: int):
    """Procura a casa vazia mais próxima de (col, lin), base 0."""
    ocupadas = {tuple(c.pos) for c in jogo.comb if c.vivo}
    for raio in range(0, 13):
        for dc in range(-raio, raio + 1):
            for dl in range(-raio, raio + 1):
                p = (col + dc, lin + dl)
                if max(abs(dc), abs(dl)) == raio and 0 <= p[0] < render.COLS and 0 <= p[1] < render.ROWS \
                        and p not in ocupadas:
                    return p
    return (col, lin)


class Combate:
    def __init__(self):
        self.comb: list[engine.Combatente] = []
        self.ordem: list[engine.Combatente] = []
        self.i = 0
        self.rodada = 1
        self.mov_restante = 5
        self.local = "billy_landia"           # fundo do mapa
        self.vagas = 10                       # vagas de jogador (o narrador muda com /combate vagas)

    @property
    def atual(self):
        return self.ordem[self.i] if self.ordem else None

    def por_nome(self, nome):
        return next((c for c in self.comb if c.nome == nome), None)

    def por_usuario(self, uid):
        return next((c for c in self.comb if c.dono_id == uid), None)


JOGOS: dict[int, Combate] = {}


def imagens(jogo: Combate):
    engine.atribuir_parties(jogo.comb)          # a cor de cada Party é definida pela ordem de entrada
    mapa = discord.File(render.para_bytes(render.desenhar_mapa(
        jogo.comb, destaque=jogo.atual, local=jogo.local)), "mapa.png")
    painel = discord.File(render.para_bytes(render.desenhar_painel(
        jogo.comb, f"Rodada {jogo.rodada}", f"Vez de {jogo.atual.nome}" if jogo.atual else "",
        ativo=jogo.atual, local=jogo.local)), "painel.png")
    return [mapa, painel]


def e_narrador(inter: discord.Interaction) -> bool:
    return any(r.name == STAFF_ROLE for r in getattr(inter.user, "roles", [])) \
        or inter.user.guild_permissions.administrator


class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()


bot = Bot()


# ------------------------------------------------------------ combate: preparação
grupo = app_commands.Group(name="combate", description="Controle do combate (narrador)")


@grupo.command(name="entrar", description="Coloca um jogador no combate")
async def entrar(inter: discord.Interaction, jogador: discord.Member, coluna: int = 10, linha: int = 5):
    if not e_narrador(inter):
        return await inter.response.send_message("Só o narrador.", ephemeral=True)
    ficha = carregar_fichas().get(str(jogador.id))
    if not ficha:
        return await inter.response.send_message("Esse jogador não tem ficha.", ephemeral=True)
    jogo = JOGOS.setdefault(inter.channel_id, Combate())
    if jogo.por_usuario(jogador.id):
        return await inter.response.send_message("Esse jogador já está na luta.", ephemeral=True)
    erro = engine.cabe_na_luta(jogo.vagas, jogo.comb, 1)
    if erro:
        return await inter.response.send_message(erro, ephemeral=True)
    jogo.comb.append(combatente_da_ficha(jogador.id, ficha, casa_livre(jogo, coluna - 1, linha - 1)))
    await inter.response.send_message(f"{ficha['nome']} entrou no combate.")


@grupo.command(name="entrar_party", description="Coloca uma Party inteira no combate (só entra se couber nas vagas)")
async def entrar_party(inter: discord.Interaction, party: str):
    if not e_narrador(inter):
        return await inter.response.send_message("Só o narrador.", ephemeral=True)
    alvo = aparencias.normalizar(party)
    membros = [(uid, f) for uid, f in carregar_fichas().items() if aparencias.normalizar(f.get("party") or "") == alvo]
    if not membros:
        return await inter.response.send_message("Não achei essa Party.", ephemeral=True)
    jogo = JOGOS.setdefault(inter.channel_id, Combate())
    novos = [(uid, f) for uid, f in membros if not jogo.por_usuario(int(uid))]
    erro = engine.cabe_na_luta(jogo.vagas, jogo.comb, len(novos))
    if erro:
        return await inter.response.send_message(erro, ephemeral=True)
    for k, (uid, f) in enumerate(novos):
        jogo.comb.append(combatente_da_ficha(int(uid), f, casa_livre(jogo, 11, 2 + k)))
    await inter.response.send_message(f"Party **{party}** entrou: " + ", ".join(f["nome"] for _, f in novos))


@grupo.command(name="vagas", description="Define quantas vagas de jogador a luta tem (1 a 10)")
async def vagas(inter: discord.Interaction, total: app_commands.Range[int, 1, 10]):
    if not e_narrador(inter):
        return await inter.response.send_message("Só o narrador.", ephemeral=True)
    jogo = JOGOS.setdefault(inter.channel_id, Combate())
    jogo.vagas = total
    await inter.response.send_message(f"A luta agora tem {total} vaga(s) de jogador.")


@grupo.command(name="local", description="Troca o fundo do mapa")
@app_commands.choices(fundo=[app_commands.Choice(name=v["nome"], value=k) for k, v in render.LOCAIS.items()])
async def local(inter: discord.Interaction, fundo: app_commands.Choice[str]):
    if not e_narrador(inter):
        return await inter.response.send_message("Só o narrador.", ephemeral=True)
    JOGOS.setdefault(inter.channel_id, Combate()).local = fundo.value
    await inter.response.send_message(f"Fundo do mapa: {fundo.name}.")


@grupo.command(name="ativo", description="Liga ou desliga uma etiqueta de algo ativo (ex.: Camuflagem)")
async def ativo(inter: discord.Interaction, alvo: str, texto: str):
    if not e_narrador(inter):
        return await inter.response.send_message("Só o narrador.", ephemeral=True)
    jogo = JOGOS.get(inter.channel_id)
    c = jogo.por_nome(alvo) if jogo else None
    if not c:
        return await inter.response.send_message("Alvo não encontrado.", ephemeral=True)
    if texto in c.ativos_extra:
        c.ativos_extra.remove(texto)
        msg = f"{texto} desligado em {c.nome}."
    else:
        c.ativos_extra.append(texto)
        msg = f"{texto} ligado em {c.nome}."
    await inter.response.send_message(msg)


@grupo.command(name="inimigo", description="Adiciona um inimigo/NPC")
@app_commands.choices(org=[app_commands.Choice(name="Cartolas", value="cartolas"),
                           app_commands.Choice(name="Billy Spaces", value="billy_spaces")])
async def inimigo(inter: discord.Interaction, nome: str, hp: int, poder: int, forca: int,
                  resistencia: int, velocidade: int, coluna: int = 3, linha: int = 3,
                  org: app_commands.Choice[str] | None = None, rank_cartola: app_commands.Range[int, 0, 3] = 0):
    if not e_narrador(inter):
        return await inter.response.send_message("Só o narrador.", ephemeral=True)
    jogo = JOGOS.setdefault(inter.channel_id, Combate())
    jogo.comb.append(engine.Combatente(
        nome, "B", dict(forca=forca, resistencia=resistencia, velocidade=velocidade, mira=0, mana=300, poder=poder),
        ["ataque_basico", "bola_de_fogo"], hp_max=hp, pos=casa_livre(jogo, coluna - 1, linha - 1),
        org=org.value if org else None, org_rank=rank_cartola))
    await inter.response.send_message(f"{nome} apareceu.")


@grupo.command(name="comecar", description="Rola a iniciativa e começa")
async def comecar(inter: discord.Interaction):
    if not e_narrador(inter):
        return await inter.response.send_message("Só o narrador.", ephemeral=True)
    jogo = JOGOS.get(inter.channel_id)
    if not jogo or not jogo.comb:
        return await inter.response.send_message("Ninguém no combate.", ephemeral=True)
    jogo.ordem = engine.ordem_iniciativa(jogo.comb)
    jogo.i, jogo.rodada = 0, 1
    await anunciar_turno(inter, jogo, [])


bot.tree.add_command(grupo)


async def anunciar_turno(inter, jogo: Combate, log: list[str]):
    c = jogo.atual
    efeitos_log, pular = engine.iniciar_turno(c)
    log += efeitos_log
    jogo.mov_restante = engine.movimento_max(c)
    cab = f"### 🎲 Vez de {c.nome} · Rodada {jogo.rodada}\n" + "\n".join(log)
    cab += f"\nMovimento: {jogo.mov_restante} casas · mana: {c.mana_turnos} turnos"
    if c.dono_id:
        cab += f"\n<@{c.dono_id}> · é a sua vez. Use `/atacar` ou mova-se."
    view = MoverView(jogo) if c.dono_id and not pular else None
    enviar = inter.followup.send if inter.response.is_done() else inter.response.send_message
    await enviar(cab, files=imagens(jogo), view=view)
    if pular or not c.vivo:
        await passar_turno(inter, jogo, [])


async def passar_turno(inter, jogo: Combate, log: list[str]):
    vivos = [c for c in jogo.ordem if c.vivo]
    if not any(c.equipe == "A" for c in vivos) or not any(c.equipe == "B" for c in vivos):
        venceu = "Jogadores" if any(c.equipe == "A" for c in vivos) else "Inimigos"
        return await inter.followup.send(f"🏁 Fim do combate. Vitória: **{venceu}**.")
    for _ in range(len(jogo.ordem)):
        jogo.i = (jogo.i + 1) % len(jogo.ordem)
        if jogo.i == 0:
            jogo.rodada += 1
        if jogo.atual.vivo:
            break
    await anunciar_turno(inter, jogo, log)
    c = jogo.atual
    if c.vivo and not c.dono_id:
        await turno_npc(inter, jogo)


async def turno_npc(inter, jogo: Combate):
    c = jogo.atual
    inimigos = [x for x in jogo.comb if x.equipe != c.equipe and x.vivo]
    aliados = [x for x in jogo.comb if x.equipe == c.equipe]
    usaveis = [engine.TECNICAS[t] for t in c.tecnicas if engine.validar(c, engine.TECNICAS[t], aliados) is None]
    if not inimigos or not usaveis:
        return await passar_turno(inter, jogo, [])
    await executar_ataque(inter, jogo, c, random.choice(inimigos), random.choice(usaveis))


# ------------------------------------------------------------ movimento
DIRS = {"↖": (-1, -1), "⬆": (0, -1), "↗": (1, -1), "⬅": (-1, 0), "➡": (1, 0),
        "↙": (-1, 1), "⬇": (0, 1), "↘": (1, 1)}


class MoverView(discord.ui.View):
    def __init__(self, jogo: Combate):
        super().__init__(timeout=900)
        self.jogo = jogo
        ordem = ["↖", "⬆", "↗", "⬅", "OK", "➡", "↙", "⬇", "↘"]
        for n, simbolo in enumerate(ordem):
            b = discord.ui.Button(label="✔" if simbolo == "OK" else simbolo, row=n // 3,
                                  style=discord.ButtonStyle.success if simbolo == "OK" else discord.ButtonStyle.secondary)
            b.callback = self.fazer_callback(simbolo)
            self.add_item(b)

    def fazer_callback(self, simbolo):
        async def cb(inter: discord.Interaction):
            c = self.jogo.atual
            if inter.user.id != c.dono_id:
                return await inter.response.send_message("Não é a sua vez.", ephemeral=True)
            if simbolo == "OK":
                self.stop()
                return await inter.response.edit_message(view=None)
            dx, dy = DIRS[simbolo]
            x, y = c.pos[0] + dx, c.pos[1] + dy
            ocupado = any(o is not c and o.vivo and o.pos == (x, y) for o in self.jogo.comb)
            if not (0 <= x < render.COLS and 0 <= y < render.ROWS) or ocupado or self.jogo.mov_restante <= 0:
                return await inter.response.send_message("Movimento inválido.", ephemeral=True)
            c.pos = (x, y)
            self.jogo.mov_restante -= 1
            await inter.response.edit_message(
                content=f"{c.nome} foi para **{render.nome_casa(c.pos)}** "
                        f"· restam {self.jogo.mov_restante} casas.",
                attachments=imagens(self.jogo), view=self)
        return cb


# ------------------------------------------------------------ /atacar tecnica: alvo:
async def tecnica_autocomplete(inter: discord.Interaction, atual: str):
    jogo = JOGOS.get(inter.channel_id)
    c = jogo.por_usuario(inter.user.id) if jogo else None
    if not c:
        return []
    aliados = [x for x in jogo.comb if x.equipe == c.equipe]
    opcoes = []
    for tid in c.tecnicas:
        t = engine.TECNICAS[tid]
        if atual.lower() in t["nome"].lower() and engine.validar(c, t, aliados) is None:
            opcoes.append(app_commands.Choice(name=f"{t['nome']} (mana {t.get('custo_mana', 0)})", value=tid))
    return opcoes[:25]


async def alvo_autocomplete(inter: discord.Interaction, atual: str):
    jogo = JOGOS.get(inter.channel_id)
    if not jogo:
        return []
    return [app_commands.Choice(name=c.nome, value=c.nome) for c in jogo.comb
            if c.vivo and atual.lower() in c.nome.lower()][:25]


@bot.tree.command(name="atacar", description="Ataca um alvo com uma técnica")
@app_commands.autocomplete(tecnica=tecnica_autocomplete, alvo=alvo_autocomplete)
async def atacar(inter: discord.Interaction, tecnica: str, alvo: str):
    jogo = JOGOS.get(inter.channel_id)
    if not jogo or not jogo.atual:
        return await inter.response.send_message("Não há combate aqui.", ephemeral=True)
    c = jogo.atual
    if c.dono_id != inter.user.id:
        return await inter.response.send_message("Não é a sua vez.", ephemeral=True)
    t = engine.TECNICAS.get(tecnica)
    alvo_c = jogo.por_nome(alvo)
    if not t or not alvo_c or not alvo_c.vivo:
        return await inter.response.send_message("Técnica ou alvo inválido.", ephemeral=True)
    erro = engine.validar(c, t, [x for x in jogo.comb if x.equipe == c.equipe])
    if erro:
        return await inter.response.send_message(erro, ephemeral=True)
    await executar_ataque(inter, jogo, c, alvo_c, t)


async def executar_ataque(inter, jogo: Combate, c, alvo, t):
    ataque = engine.rolar_ataque(c, t)
    areas = [alvo]
    if t.get("area"):
        areas += [x for x in jogo.comb if x is not alvo and x.vivo and x.equipe == alvo.equipe
                  and max(abs(x.pos[0] - alvo.pos[0]), abs(x.pos[1] - alvo.pos[1])) <= t["area"]]
    # defensor humano escolhe; NPC esquiva sozinho
    if alvo.dono_id and ataque.tier > 0:
        view = ReacaoView(jogo, c, alvo, t, ataque, areas)
        msg = (f"⚔️ **{c.nome}** usou **{t['nome']}** em {alvo.nome} "
               f"(d20 {ataque.natural} → {ataque.total}: {engine.TIER_NOME[ataque.tier]}).\n"
               f"<@{alvo.dono_id}>, escolha sua reação (2 min):")
        enviar = inter.followup.send if inter.response.is_done() else inter.response.send_message
        return await enviar(msg, view=view)
    log = []
    for a in areas:
        log += engine.resolver(c, a, t, ataque, "esquiva")
    enviar = inter.followup.send if inter.response.is_done() else inter.response.send_message
    await enviar("\n".join(log))
    await passar_turno(inter, jogo, [])


class ReacaoView(discord.ui.View):
    def __init__(self, jogo, atacante, alvo, t, ataque, areas):
        super().__init__(timeout=120)
        self.jogo, self.atacante, self.alvo, self.t, self.ataque, self.areas = jogo, atacante, alvo, t, ataque, areas
        self.resolvido = False

    async def _resolver(self, inter: discord.Interaction, reacao: str):
        if inter.user.id != self.alvo.dono_id:
            return await inter.response.send_message("Essa reação não é sua.", ephemeral=True)
        if self.resolvido:
            return
        self.resolvido = True
        log = []
        for a in self.areas:
            log += engine.resolver(self.atacante, a, self.t, self.ataque, reacao)
        await inter.response.edit_message(content="\n".join(log), view=None)
        await passar_turno(inter, self.jogo, [])

    @discord.ui.button(label="Esquivar", style=discord.ButtonStyle.primary, emoji="💨")
    async def esquivar(self, inter, _):
        await self._resolver(inter, "esquiva")

    @discord.ui.button(label="Bloquear", style=discord.ButtonStyle.secondary, emoji="🛡️")
    async def bloquear(self, inter, _):
        await self._resolver(inter, "bloqueio")

    async def on_timeout(self):
        # sem resposta: esquiva automática (o narrador pode mudar isso)
        pass


@bot.tree.command(name="passar", description="Encerra seu turno sem atacar")
async def passar(inter: discord.Interaction):
    jogo = JOGOS.get(inter.channel_id)
    if not jogo or not jogo.atual or jogo.atual.dono_id != inter.user.id:
        return await inter.response.send_message("Não é a sua vez.", ephemeral=True)
    await inter.response.send_message(f"{jogo.atual.nome} passou o turno.")
    await passar_turno(inter, jogo, [])


@bot.tree.command(name="ficha", description="Mostra sua ficha")
async def ficha(inter: discord.Interaction):
    f = carregar_fichas().get(str(inter.user.id))
    if not f:
        return await inter.response.send_message("Você ainda não tem ficha.", ephemeral=True)
    linhas = [f"**{f['nome']}**"] + [f"{k}: {v} ({engine.rank_nome(v)})" for k, v in f["stats"].items()]
    linhas.append("Técnicas: " + ", ".join(engine.TECNICAS[t]["nome"] for t in f["tecnicas"]))
    await inter.response.send_message("\n".join(linhas), ephemeral=True)


# ------------------------------------------------------------ /aparencia
class ConfirmarParecido(discord.ui.View):
    """O bot achou algo parecido: o jogador diz se é o mesmo; se não for, o narrador aprova."""
    def __init__(self, dono: discord.abc.User, personagem, obra, imagem: bytes, parecido: dict):
        super().__init__(timeout=300)
        self.dono, self.personagem, self.obra, self.imagem, self.parecido = dono, personagem, obra, imagem, parecido

    @discord.ui.button(label="É o mesmo", style=discord.ButtonStyle.danger)
    async def mesmo(self, inter: discord.Interaction, _):
        if inter.user.id != self.dono.id:
            return await inter.response.send_message("Esse pedido não é seu.", ephemeral=True)
        self.stop()
        await inter.response.edit_message(content="Então essa aparência já está em uso. Escolha outro personagem.", view=None)

    @discord.ui.button(label="É outro personagem", style=discord.ButtonStyle.secondary)
    async def outro(self, inter: discord.Interaction, _):
        if inter.user.id != self.dono.id:
            return await inter.response.send_message("Esse pedido não é seu.", ephemeral=True)
        self.stop()
        view = AprovarAparencia(self.dono, self.personagem, self.obra, self.imagem)
        await inter.response.edit_message(
            content=f"Pedido enviado ao narrador: **{self.personagem} ({self.obra})**, parecido com "
                    f"**{self.parecido['personagem']} ({self.parecido['obra']})**.", view=view)


class AprovarAparencia(discord.ui.View):
    def __init__(self, dono, personagem, obra, imagem: bytes):
        super().__init__(timeout=None)
        self.dono, self.personagem, self.obra, self.imagem = dono, personagem, obra, imagem

    @discord.ui.button(label="Aprovar (narrador)", style=discord.ButtonStyle.success)
    async def aprovar(self, inter: discord.Interaction, _):
        if not e_narrador(inter):
            return await inter.response.send_message("Só o narrador.", ephemeral=True)
        guardar_aparencia(self.dono.id, self.personagem, self.obra, self.imagem)
        self.stop()
        await inter.response.edit_message(content=f"✅ Aprovado: {self.dono.mention} agora é **{self.personagem} ({self.obra})**.", view=None)

    @discord.ui.button(label="Recusar (narrador)", style=discord.ButtonStyle.danger)
    async def recusar(self, inter: discord.Interaction, _):
        if not e_narrador(inter):
            return await inter.response.send_message("Só o narrador.", ephemeral=True)
        self.stop()
        await inter.response.edit_message(content=f"❌ Recusado: {self.personagem} ({self.obra}).", view=None)


def guardar_aparencia(uid: int, personagem: str, obra: str, imagem: bytes):
    fichas = carregar_fichas()
    ficha = fichas.get(str(uid))
    if not ficha:
        return None
    if ficha.get("aparencia_id"):
        aparencias.liberar(ficha["aparencia_id"])     # a aparência antiga volta a ficar livre
    reg = aparencias.registrar(personagem, obra, imagem, uid)
    ficha["aparencia_id"] = reg["id"]
    salvar_fichas(fichas)
    return reg


@bot.tree.command(name="aparencia", description="Escolhe a aparência do seu personagem (ex.: Sasuke, Naruto)")
async def aparencia(inter: discord.Interaction, personagem: str, obra: str, imagem: discord.Attachment):
    if str(inter.user.id) not in carregar_fichas():
        return await inter.response.send_message("Você ainda não tem ficha.", ephemeral=True)
    if not (imagem.content_type or "").startswith("image/"):
        return await inter.response.send_message("Mande uma imagem (png, jpg ou webp).", ephemeral=True)
    dados = await imagem.read()
    veredito, achados = aparencias.checar(personagem, obra, ignorar_dono=inter.user.id)
    if veredito == "igual":
        a = achados[0]
        return await inter.response.send_message(
            f"**{a['personagem']} ({a['obra']})** já está em uso por <@{a['dono_id']}>. Escolha outro personagem.",
            ephemeral=True)
    if veredito == "parecido":
        a = achados[0]
        return await inter.response.send_message(
            f"Já existe **{a['personagem']} ({a['obra']})** em uso. É o mesmo personagem que você escreveu?",
            view=ConfirmarParecido(inter.user, personagem, obra, dados, a), ephemeral=True)
    guardar_aparencia(inter.user.id, personagem, obra, dados)
    await inter.response.send_message(f"Aparência salva: **{personagem} ({obra})**.", ephemeral=True)


@bot.tree.command(name="aparencia_liberar", description="Libera uma aparência presa (narrador)")
async def aparencia_liberar(inter: discord.Interaction, personagem: str, obra: str):
    if not e_narrador(inter):
        return await inter.response.send_message("Só o narrador.", ephemeral=True)
    veredito, achados = aparencias.checar(personagem, obra)
    if not achados:
        return await inter.response.send_message("Não achei essa aparência.", ephemeral=True)
    a = achados[0]
    aparencias.liberar(a["id"])
    fichas = carregar_fichas()
    ficha = fichas.get(str(a["dono_id"]))
    if ficha and ficha.get("aparencia_id") == a["id"]:
        ficha["aparencia_id"] = None
        salvar_fichas(fichas)
    await inter.response.send_message(f"Liberada: {a['personagem']} ({a['obra']}).")


if __name__ == "__main__":
    caminhos.preparar()
    bot.run(os.environ["DISCORD_TOKEN"])
