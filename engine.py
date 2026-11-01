"""Motor de combate do RP Billy. Sem Discord: só regras, em cima de dados JSON."""
from __future__ import annotations
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

DATA = Path(__file__).parent


def _carregar(nome):
    return json.loads((DATA / nome).read_text(encoding="utf-8"))


TECNICAS = _carregar("tecnicas.json")
EFEITOS = _carregar("efeitos.json")
PASSIVAS = _carregar("passivas.json")
for _k, _v in TECNICAS.items():
    _v["id"] = _k

# ---------------------------------------------------------------- ranks
RANKS = [("-C", 100), ("C", 200), ("+C", 300), ("-B", 400), ("B", 500), ("+B", 600),
         ("-A", 700), ("A", 800), ("+A", 900), ("-S", 1000), ("S", 1250), ("+S", 1500),
         ("SSS", 2000)]
BUFF = {"C": 1, "B": 2, "A": 3, "S": 4, "SSS": 5}
ROLL_MULT = {1: 1.0, 2: 1.5, 3: 2.0}
TIER_NOME = {0: "errou", 1: "acertou", 2: "ataque poderoso", 3: "CRÍTICO"}
ESCALA_PADRAO = {"melee": "forca", "range": "poder", "arma": "mira"}


def rank_index(pontos: float) -> int:
    idx = 0
    for i, (_, minimo) in enumerate(RANKS, 1):
        if pontos >= minimo:
            idx = i
    return idx


def rank_nome(pontos: float) -> str:
    i = rank_index(pontos)
    return RANKS[i - 1][0] if i else "—"


def rank_buff(pontos: float) -> int:
    return BUFF.get(rank_nome(pontos).strip("+-"), 0)


# ---------------------------------------------------------------- combatente
@dataclass
class Combatente:
    nome: str
    equipe: str                      # "A" (jogadores), "B" (inimigos)
    stats: dict                      # forca, resistencia, velocidade, mira, mana, poder
    tecnicas: list = field(default_factory=lambda: ["ataque_basico"])
    passivas: list = field(default_factory=list)
    pos: tuple = (0, 0)              # (coluna, linha), base 0
    dono_id: int | None = None       # id do usuário no Discord (None = NPC)
    hp_max: float = 0
    hp: float = 0
    mana_turnos: int = 0
    efeitos: list = field(default_factory=list)
    recargas: dict = field(default_factory=dict)
    # identidade e exibição (usados só pelas imagens e pelas regras de Party)
    familia: str = ""
    raca: str = ""
    org: str | None = None           # "billy_spaces" | "cartolas" | None (civil)
    org_rank: int = 0                # cartolas: 0 aprendiz, 1 chefe (amarela), 2 elite (azul), 3 mister (vermelha)
    party: str | None = None
    party_n: int = 0                 # posição da Party na luta (define a cor)
    avatar: object = None            # imagem PIL da /aparencia
    ativos_extra: list = field(default_factory=list)   # técnicas/transformações ligadas, só texto

    def __post_init__(self):
        if not self.hp_max:
            self.hp_max = round(100 + 0.6 * self.stats.get("resistencia", 0))
        if not self.hp:
            self.hp = self.hp_max
        extra = sum(PASSIVAS.get(p, {}).get("mana_turnos", 0) for p in self.passivas)
        self.mana_turnos = int(self.stats.get("mana", 0) // 100) + extra
        self.mana_max = self.mana_turnos

    @property
    def vivo(self) -> bool:
        return self.hp > 0

    @property
    def categoria(self) -> int:
        return rank_index(max(self.stats.values()))


# ---------------------------------------------------------------- bônus
def _mods(c: Combatente, chave: str) -> int:
    total = 0
    for p in c.passivas:
        total += PASSIVAS.get(p, {}).get("mods", {}).get(chave, 0)
    for e in c.efeitos:
        total += EFEITOS[e["id"]].get("mods", {}).get(chave, 0)
    return total


def resistencia_a(c: Combatente, tag: str) -> int:
    return sum(PASSIVAS.get(p, {}).get("resist", {}).get(tag, 0) for p in c.passivas)


def bonus_ataque(c: Combatente, t: dict) -> int:
    stat = t.get("escala", ESCALA_PADRAO[t["tipo"]])
    return rank_buff(c.stats.get(stat, 0)) + _mods(c, "ataque") + t.get("bonus_ataque", 0)


def bonus_defesa(c: Combatente, reacao: str, tag: str) -> int:
    stat = "velocidade" if reacao == "esquiva" else "resistencia"
    return rank_buff(c.stats.get(stat, 0)) + _mods(c, reacao) + resistencia_a(c, tag)


def mult_categoria(a: Combatente, d: Combatente) -> float:
    diff = a.categoria - d.categoria
    return max(0.5, min(2.5, 1 + 0.10 * diff))


# ---------------------------------------------------------------- rolls
@dataclass
class Ataque:
    natural: int
    total: int
    tier: int        # 0 errou, 1 acertou, 2 poderoso, 3 crítico


def rolar_ataque(c: Combatente, t: dict, rng=random) -> Ataque:
    nat = rng.randint(1, 20)
    total = nat + bonus_ataque(c, t)
    if nat == 20:
        tier = 3
    elif nat == 1:
        tier = 0
    else:
        tier = 0 if total < 10 else 1 if total < 15 else 2 if total < 20 else 3
    return Ataque(nat, total, tier)


def pct_esquiva(total: int, tier: int) -> float:
    """Fração do dano que o defensor ainda toma ao esquivar."""
    if total >= 20:
        return 0.0
    if total >= 15:
        return 0.0 if tier <= 2 else 1.0
    if total >= 10:
        return 0.0 if tier <= 1 else 1.0
    if total >= 5:
        return 0.5          # sacrificou algo para tomar menos
    return 1.0


def pct_bloqueio(total: int, tier: int, atk_total: int) -> float:
    if total < 5:
        return 1.0
    if total < 10:
        return 0.75 if tier == 1 else 1.0
    if total < 15:
        return 0.25 if tier <= 2 else 1.0
    if total < 20:
        return {1: 0.0, 2: 0.25, 3: 0.75}[tier]
    if tier <= 2:
        return 0.0
    return 0.0 if total > atk_total else 0.25


# ---------------------------------------------------------------- validação
def validar(c: Combatente, t: dict, aliados: list) -> str | None:
    if t["id"] not in c.tecnicas:
        return "Você não tem essa técnica."
    if t.get("custo_mana", 0) > c.mana_turnos:
        return "Sem turnos de mana suficientes."
    r = c.recargas.get(t["id"], 0)
    if r > 0:
        return f"Em recarga ({r} turno(s))."
    cond = t.get("condicao")
    if cond and "hp_abaixo_pct" in cond:
        if not any(a.vivo and a.hp / a.hp_max < cond["hp_abaixo_pct"] for a in aliados):
            return "Requer você ou um aliado com pouca vida."
    return None


# ---------------------------------------------------------------- resolução
def aplicar_efeito(alvo: Combatente, efeito_id: str, turnos: int):
    for e in alvo.efeitos:
        if e["id"] == efeito_id:
            e["turnos"] = max(e["turnos"], turnos)
            return
    alvo.efeitos.append({"id": efeito_id, "turnos": turnos})


def resolver(att: Combatente, alvo: Combatente, t: dict, ataque: Ataque,
             reacao: str = "esquiva", rng=random) -> list[str]:
    """Gasta recursos, rola a defesa, calcula dano e efeitos. Devolve linhas de log."""
    log = []
    att.mana_turnos -= t.get("custo_mana", 0)
    if t.get("recarga"):
        att.recargas[t["id"]] = t["recarga"] + 1   # +1: o próprio fim do turno desconta
    log.append(f"⚔️ **{att.nome}** usou **{t['nome']}** em **{alvo.nome}** "
               f"(d20 {ataque.natural} → {ataque.total}: {TIER_NOME[ataque.tier]})")
    if ataque.tier == 0:
        return log

    tag = t.get("elemento", "fisico")
    cat = mult_categoria(att, alvo)
    stat = t.get("escala", ESCALA_PADRAO[t["tipo"]])
    for i in range(t.get("golpes", 1)):
        nat = rng.randint(1, 20)
        total = nat + bonus_defesa(alvo, reacao, tag)
        if nat == 20:
            total = max(total, 20)
        if reacao == "esquiva":
            taken = pct_esquiva(total, ataque.tier)
        else:
            taken = pct_bloqueio(total, ataque.tier, ataque.total)
        nome_r = "esquivou" if reacao == "esquiva" else "bloqueou"
        prefixo = f"golpe {i + 1}: " if t.get("golpes", 1) > 1 else ""
        if taken == 0:
            log.append(f"🛡️ {prefixo}{alvo.nome} {nome_r} tudo (d20 {nat} → {total}).")
            continue
        base = t["dano_base"] + att.stats.get(stat, 0) * t.get("coef", 0.05)
        dano = round(base * ROLL_MULT[ataque.tier] * cat * taken)
        alvo.hp = max(0, alvo.hp - dano)
        parte = "" if taken == 1 else f" (tomou {int(taken * 100)}%)"
        log.append(f"💥 {prefixo}{alvo.nome} {nome_r} (d20 {nat} → {total}){parte} e recebeu **{dano}** de dano.")
        for ef in t.get("efeitos", []):
            chance = ef["chance"] - 0.10 * resistencia_a(alvo, ef.get("tag", tag))
            if alvo.vivo and rng.random() < chance:
                aplicar_efeito(alvo, ef["id"], ef["turnos"])
                d = EFEITOS[ef["id"]]
                log.append(f"{d['emoji']} {alvo.nome} recebeu **{d['nome']}** ({ef['turnos']}t).")
        if not alvo.vivo:
            log.append(f"☠️ **{alvo.nome}** caiu!")
            break
    return log


# ---------------------------------------------------------------- turnos
def iniciar_turno(c: Combatente) -> tuple[list[str], bool]:
    """Aplica efeitos no começo do turno. Devolve (log, pula_turno)."""
    log, pular = [], False
    for k in list(c.recargas):
        c.recargas[k] -= 1
        if c.recargas[k] <= 0:
            del c.recargas[k]
    for e in list(c.efeitos):
        d = EFEITOS[e["id"]]
        if d.get("tick_pct"):
            dano = round(c.hp_max * d["tick_pct"])
            c.hp = max(0, c.hp - dano)
            log.append(f"{d['emoji']} {c.nome} sofreu {dano} de {d['nome'].lower()}.")
        if d.get("pula_turno"):
            pular = True
            log.append(f"{d['emoji']} {c.nome} está {d['nome'].lower()} e perde o turno.")
        e["turnos"] -= 1
        if e["turnos"] <= 0:
            c.efeitos.remove(e)
            log.append(f"{d['emoji']} {d['nome']} em {c.nome} acabou.")
    if not c.vivo:
        log.append(f"☠️ **{c.nome}** caiu!")
    return log, pular


def ordem_iniciativa(combatentes: list[Combatente], rng=random) -> list[Combatente]:
    return sorted(combatentes, key=lambda c: c.stats.get("velocidade", 0) + rng.randint(1, 20),
                  reverse=True)


def movimento_max(c: Combatente) -> int:
    return max(0, 5 + _mods(c, "movimento"))


# ---------------------------------------------------------------- party e vagas
def atribuir_parties(combatentes: list[Combatente]):
    """Numera as Parties na ordem de entrada; o número decide a cor. Quem joga sem Party conta como uma Party de 1."""
    ordem: list = []
    for c in combatentes:
        if c.equipe != "A":
            continue
        chave = c.party or ("solo", c.nome)
        if chave not in ordem:
            ordem.append(chave)
        c.party_n = ordem.index(chave)


def vagas_livres(total_vagas: int, combatentes: list[Combatente]) -> int:
    return total_vagas - sum(1 for c in combatentes if c.dono_id)


def cabe_na_luta(total_vagas: int, combatentes: list[Combatente], novos: int) -> str | None:
    """None se a Party inteira cabe; senão a mensagem de erro."""
    livres = vagas_livres(total_vagas, combatentes)
    if novos > livres:
        return f"A Party tem {novos} jogador(es) e só restam {livres} vaga(s) de {total_vagas}."
    return None
