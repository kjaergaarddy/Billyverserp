# Billyversebot (protótipo)

## O que tem
- `engine.py`: regras (d20, esquiva/bloqueio, categorias, dano, efeitos, turnos, vagas e Parties). Testado com uma simulação de combate.
- `tecnicas.json`, `efeitos.json`, `passivas.json`: técnicas, efeitos e passivas. É aqui que você cria/ajusta coisas, sem mexer em código.
- `render.py`: mapa e painel de combate (imagens). Fontes: os arquivos `.ttf` ao lado.
- `aparencias.py`: repositório do `/aparencia`, tolera erro de escrita no nome e na obra.
- `bot.py`: comandos do Discord (ainda NÃO testado num servidor de verdade).
- `fichas.json`: modelo de ficha (chave = ID do Discord). O bot copia para a pasta de dados na 1ª vez.
- `caminhos.py`: onde ficam fichas e aparências (variável `DATA_DIR`, ver abaixo).

## Comandos
- Narrador: `/combate entrar`, `/combate entrar_party`, `/combate inimigo`, `/combate vagas`,
  `/combate local` (fundo do mapa), `/combate ativo` (liga/desliga etiqueta), `/combate comecar`, `/aparencia_liberar`
- Jogadores: `/atacar tecnica: alvo:`, `/passar`, `/ficha`, `/aparencia personagem: obra: imagem:`
- Botões de movimento (setas e ✔) e de reação (Esquivar/Bloquear).

## Regras que o bot aplica
- Até 10 jogadores por luta. O narrador define as vagas e uma Party só entra se couber inteira nas vagas livres.
- A cor de cada Party vem da ordem de entrada (10 cores). Quem joga sem Party conta como uma Party de 1.
- Inimigos e NPCs ficam sempre em vermelho-sangue, fora das Parties.
- `/aparencia`: cada personagem (de qualquer obra) só pode ser usado por um jogador. Se o nome for parecido
  com outro já usado, o bot pergunta "é o mesmo?". Se o jogador disser que é outro, o narrador aprova ou recusa.

## Como rodar
1. Crie o bot em discord.com/developers, copie o token e convide para o servidor (escopo `bot` + `applications.commands`).
2. `pip install -U -r requirements.txt`
3. `DISCORD_TOKEN=seu_token python bot.py`
4. Crie o cargo "Narrador" no servidor (ou use um admin).
5. No Railway: crie um Volume montado em `/dados` e adicione a variável `DATA_DIR=/dados`. Sem isso, fichas e aparências somem quando o bot reinicia.

## Para criar uma técnica nova
Copie uma entrada de `tecnicas.json` e mude: nome, tipo (melee/range/arma), dano_base, coef,
custo_mana, recarga, elemento, efeitos. Pronto, ela já aparece no `/atacar`.

## Ainda falta
Treino, rolls de família/técnica, loja, evolução de rank, ultimate com d40, persistência do combate,
fundos de Snow Landia e Plan Landia (hoje só mudam de cor) e o desenho de cada local.
Os números de dano são estimativas e precisam de teste no RP.
