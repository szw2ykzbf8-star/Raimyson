import streamlit as st
import streamlit.components.v1 as components
from modules.auth import requer_login

usuario = requer_login()
perfil  = usuario.get("perfil", "digitador")

_PERFIL_PADRAO = {
    "admin":     {"pedidos","cotacoes","analise","ordem","recebimento","compra_avulsa","produtos","fornecedores","relatorios","configuracoes"},
    "comprador": {"pedidos","cotacoes","analise","ordem","recebimento","compra_avulsa","produtos","fornecedores","relatorios"},
    "digitador": {"pedidos"},
}
_perm_str = str(usuario.get("permissoes", "") or "").strip()
perm = {p.strip() for p in _perm_str.split(",") if p.strip()} if _perm_str else set(_PERFIL_PADRAO.get(perfil, {"pedidos"}))
if perfil == "admin":
    perm.add("configuracoes")
else:
    perm.discard("configuracoes")

st.title("📖 Central de Ajuda")
st.markdown(
    "Bem-vindo à **Central de Ajuda** do Sistema de Compras H Hotéis. "
    "Aqui você encontra orientações detalhadas sobre cada módulo, além de "
    "fluxogramas visuais com o passo a passo de cada processo."
)
st.markdown("---")


# ── Gerador de fluxograma SVG vertical ───────────────────────────────────────
def _svg_flow(steps, w=480):
    """
    Gera HTML com SVG de fluxograma vertical.
    Retorna (html_str, altura_px).

    steps: lista de dicts
      t    : "s" = oval início  |  "e" = oval fim
             "p" = retângulo processo  |  "d" = losango decisão
      text : texto da forma
      yes  : (apenas "d") rótulo da seta de continuidade (padrão "Sim")
      no   : (apenas "d") texto da ramificação lateral, use | para quebrar linhas
    """
    cx = w // 2
    OW, OH = 180, 46   # oval
    RW, RH = 280, 52   # retângulo processo
    DW, DH = 220, 60   # losango (bounding box)
    AR     = 30         # altura da seta
    GAP    = 6          # espaço após seta

    CS = "#27AE60"   # verde   — início
    CE = "#C0392B"   # vermelho — fim
    CP = "#2980B9"   # azul    — processo
    CD = "#E67E22"   # laranja  — decisão
    CA = "#444444"   # seta

    def _txt(x, y, s, fs=12, col="#fff", mw=26):
        words = str(s).split()
        lines, cur = [], ""
        for ww in words:
            test = (cur + " " + ww).strip()
            if len(test) <= mw:
                cur = test
            else:
                if cur: lines.append(cur)
                cur = ww
        if cur: lines.append(cur)
        if not lines: lines = [str(s)]
        lh = fs + 4
        sy = y - (len(lines) - 1) * lh / 2
        out = [
            f'<text text-anchor="middle" font-family="Arial,sans-serif"'
            f' font-size="{fs}" fill="{col}" font-weight="bold">'
        ]
        for i, ln in enumerate(lines):
            out.append(f'<tspan x="{x}" y="{sy + i * lh}">{ln}</tspan>')
        out.append("</text>")
        return "".join(out)

    parts = [
        '<defs><marker id="ah" markerWidth="9" markerHeight="7"'
        ' refX="8" refY="3.5" orient="auto">'
        f'<polygon points="0 0,9 3.5,0 7" fill="{CA}"/>'
        '</marker></defs>'
    ]

    y = 18
    for i, step in enumerate(steps):
        t = step["t"]
        is_last = (i == len(steps) - 1)

        if t in ("s", "e"):
            col = CS if t == "s" else CE
            cy  = y + OH // 2
            parts.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{OW//2}" ry="{OH//2}" fill="{col}"/>')
            parts.append(_txt(cx, cy, step["text"], 13))
            bot = y + OH

        elif t == "p":
            parts.append(
                f'<rect x="{cx - RW//2}" y="{y}" width="{RW}"'
                f' height="{RH}" rx="9" fill="{CP}"/>'
            )
            parts.append(_txt(cx, y + RH // 2, step["text"]))
            bot = y + RH

        elif t == "d":
            my  = y + DH // 2
            pts = f"{cx},{y} {cx+DW//2},{my} {cx},{y+DH} {cx-DW//2},{my}"
            parts.append(f'<polygon points="{pts}" fill="{CD}"/>')
            parts.append(_txt(cx, my, step["text"], 11, mw=22))
            bot = y + DH

            no_txt = step.get("no", "")
            if no_txt:
                nx = cx + DW // 2
                parts.append(
                    f'<line x1="{nx}" y1="{my}" x2="{nx+24}" y2="{my}"'
                    f' stroke="{CA}" stroke-width="1.5" stroke-dasharray="4,2"/>'
                )
                parts.append(
                    f'<text x="{nx+28}" y="{my-7}" font-size="10"'
                    f' fill="#666" font-family="Arial" font-weight="bold">Não</text>'
                )
                for li, ln in enumerate(no_txt.split("|")):
                    parts.append(
                        f'<text x="{nx+28}" y="{my+7+li*13}" font-size="10"'
                        f' fill="#555" font-family="Arial">{ln.strip()}</text>'
                    )
        else:
            bot = y

        if not is_last:
            if t == "d":
                yes_lbl = step.get("yes", "Sim")
                parts.append(
                    f'<text x="{cx+6}" y="{bot+15}" font-size="10"'
                    f' fill="#555" font-family="Arial" font-weight="bold">{yes_lbl}</text>'
                )
            parts.append(
                f'<line x1="{cx}" y1="{bot}" x2="{cx}" y2="{bot+AR-5}"'
                f' stroke="{CA}" stroke-width="2" marker-end="url(#ah)"/>'
            )
            y = bot + AR + GAP
        else:
            y = bot + 22

    svg  = f'<svg width="{w}" height="{y}" xmlns="http://www.w3.org/2000/svg">{"".join(parts)}</svg>'
    html = f'<div style="text-align:center;padding:6px 0">{svg}</div>'
    return html, y + 20


# ── Dados dos fluxogramas ─────────────────────────────────────────────────────
_FL_GERAL = [
    {"t":"s","text":"Início"},
    {"t":"p","text":"Cadastrar Produtos, Fornecedores e Unidades Hoteleiras"},
    {"t":"p","text":"Digitador cria Solicitação de Compra"},
    {"t":"p","text":"Comprador bloqueia os pedidos e vincula à Cotação"},
    {"t":"p","text":"Criar Cotação e enviar links para os Fornecedores"},
    {"t":"d","text":"Fornecedor respondeu?","yes":"Sim","no":"Não → aguardar|ou encerrar|antecipadamente"},
    {"t":"p","text":"Encerrar a Cotação"},
    {"t":"p","text":"Analisar Preços e selecionar Fornecedor por produto"},
    {"t":"p","text":"Gerar Pedido de Compra"},
    {"t":"p","text":"Baixar PDF e enviar ao Fornecedor"},
    {"t":"p","text":"Marcar pedido como Enviado"},
    {"t":"p","text":"Receber a mercadoria e importar NF-e (XML)"},
    {"t":"e","text":"Fim"},
]

_FL_PEDIDOS = [
    {"t":"s","text":"Início"},
    {"t":"p","text":"Acessar Solicitações de Compra no menu"},
    {"t":"p","text":"Aba: Nova Solicitação"},
    {"t":"p","text":"Selecionar a Unidade Hoteleira"},
    {"t":"p","text":"Informar a quantidade de cada produto necessário"},
    {"t":"d","text":"Algum produto com quantidade maior que zero?","yes":"Sim","no":"Não → revisar|as quantidades"},
    {"t":"p","text":"Clicar em Enviar Solicitação"},
    {"t":"e","text":"Fim"},
]

_FL_COTACOES = [
    {"t":"s","text":"Início"},
    {"t":"d","text":"Há pedidos bloqueados disponíveis?","yes":"Sim","no":"Não → aguardar|solicitações"},
    {"t":"p","text":"Acessar Cotações → aba Nova Cotação"},
    {"t":"p","text":"Definir nome e prazo limite da cotação"},
    {"t":"p","text":"Selecionar os fornecedores participantes"},
    {"t":"p","text":"Clicar em Iniciar Cotação"},
    {"t":"p","text":"Copiar e enviar o link para cada fornecedor"},
    {"t":"d","text":"Todos os fornecedores responderam?","yes":"Sim","no":"Não → aguardar ou|encerrar manualmente"},
    {"t":"p","text":"Encerrar a Cotação"},
    {"t":"p","text":"Ir para Análise de Preços"},
    {"t":"e","text":"Fim"},
]

_FL_ANALISE = [
    {"t":"s","text":"Início"},
    {"t":"p","text":"Acessar Análise de Preços"},
    {"t":"p","text":"Selecionar a cotação desejada"},
    {"t":"p","text":"Revisar a grade de preços e selecionar o fornecedor por produto"},
    {"t":"d","text":"Total atinge o pedido mínimo?","yes":"Sim","no":"Não → marcar|'Ignorar pedido|mínimo'"},
    {"t":"p","text":"Ajustar quantidades por Unidade Hoteleira se necessário"},
    {"t":"p","text":"Clicar em Comprar"},
    {"t":"p","text":"Baixar o PDF do pedido gerado"},
    {"t":"e","text":"Fim"},
]

_FL_ORDEM = [
    {"t":"s","text":"Início"},
    {"t":"p","text":"Acessar Ordem de Compra no menu"},
    {"t":"p","text":"Expandir o fornecedor desejado"},
    {"t":"p","text":"Clicar em Baixar pedido (imprimir / salvar PDF)"},
    {"t":"p","text":"Abrir o arquivo .html baixado no navegador"},
    {"t":"p","text":"Pressionar Ctrl+P → Salvar como PDF"},
    {"t":"p","text":"Enviar o PDF ao fornecedor"},
    {"t":"p","text":"Clicar em Marcar tudo como enviado"},
    {"t":"e","text":"Fim"},
]

_FL_RECEBIMENTO = [
    {"t":"s","text":"Início"},
    {"t":"p","text":"Acessar Recebimento NF-e no menu"},
    {"t":"p","text":"Fazer upload do arquivo XML da nota fiscal"},
    {"t":"d","text":"CNPJ do fornecedor está cadastrado?","yes":"Sim","no":"Não → cadastrar o|fornecedor antes|de prosseguir"},
    {"t":"p","text":"Conferir os itens e quantidades recebidos"},
    {"t":"p","text":"Salvar o registro de recebimento"},
    {"t":"e","text":"Fim"},
]

_FL_AVULSA = [
    {"t":"s","text":"Início"},
    {"t":"p","text":"Acessar Compra Avulsa no menu"},
    {"t":"p","text":"Fazer upload do arquivo XML da NF-e"},
    {"t":"p","text":"Revisar os itens importados da nota"},
    {"t":"p","text":"Salvar o registro"},
    {"t":"e","text":"Fim"},
]


# ── Tabs ──────────────────────────────────────────────────────────────────────
tabs_nomes = ["🗺️ Visão Geral"]
if "pedidos"       in perm: tabs_nomes.append("📋 Solicitações")
if "cotacoes"      in perm: tabs_nomes.append("💰 Cotações")
if "analise"       in perm: tabs_nomes.append("📊 Análise de Preços")
if "ordem"         in perm: tabs_nomes.append("🛒 Ordem de Compra")
if "recebimento"   in perm: tabs_nomes.append("📥 Recebimento")
if "compra_avulsa" in perm: tabs_nomes.append("🧾 Compra Avulsa")
if "produtos" in perm or "fornecedores" in perm: tabs_nomes.append("📦 Cadastros")
if "relatorios"    in perm: tabs_nomes.append("📈 Relatórios")
if "configuracoes" in perm: tabs_nomes.append("⚙️ Configurações")
tabs_nomes.append("🔑 Minha Conta")

tabs = st.tabs(tabs_nomes)
ti = {nome: obj for nome, obj in zip(tabs_nomes, tabs)}


# ══════════════════════════════════════════════════════════════════════════════
# VISÃO GERAL
# ══════════════════════════════════════════════════════════════════════════════
with ti["🗺️ Visão Geral"]:
    st.subheader("Como o sistema funciona")
    st.markdown(
        "O sistema segue um ciclo completo de compras: desde o registro da necessidade por cada "
        "unidade hoteleira até o recebimento da mercadoria com importação da nota fiscal. "
        "O fluxograma abaixo mostra todas as etapas em sequência."
    )

    _h, _ht = _svg_flow(_FL_GERAL)
    components.html(_h, height=_ht, scrolling=False)

    st.markdown("---")
    st.subheader("Perfis de acesso")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Digitador**")
        st.markdown(
            "Acesso restrito ao módulo de **Solicitações de Compra**. "
            "Responsável por registrar o que cada unidade hoteleira precisa comprar. "
            "Não visualiza preços, fornecedores ou cotações."
        )
    with col2:
        st.markdown("**Comprador**")
        st.markdown(
            "Acesso completo ao ciclo de compras: solicitações, cotações, análise de preços, "
            "ordem de compra, recebimento, compra avulsa, cadastro de produtos e fornecedores, "
            "e relatórios."
        )
    with col3:
        st.markdown("**Administrador**")
        st.markdown(
            "Tudo que o comprador acessa, mais o módulo de **Configurações** — onde é possível "
            "gerenciar unidades hoteleiras, unidades de medida, usuários, orçamentos e realizar "
            "backup dos dados. Também é o único perfil que pode **excluir cotações**."
        )

    st.markdown("---")
    st.info(
        "💡 **Dica:** As abas desta Central de Ajuda exibem apenas os módulos que o seu "
        "perfil tem permissão para acessar."
    )


# ══════════════════════════════════════════════════════════════════════════════
# SOLICITAÇÕES
# ══════════════════════════════════════════════════════════════════════════════
if "📋 Solicitações" in ti:
    with ti["📋 Solicitações"]:
        st.subheader("Solicitações de Compra")
        st.markdown(
            "Este módulo é o ponto de partida do processo. É aqui que cada unidade hoteleira "
            "registra os produtos que precisa comprar antes que uma cotação seja gerada. "
            "O responsável informa apenas as quantidades — a escolha de fornecedor e preços "
            "é feita pelo comprador nas etapas seguintes."
        )

        st.markdown("**Fluxo desta etapa:**")
        _h, _ht = _svg_flow(_FL_PEDIDOS)
        components.html(_h, height=_ht, scrolling=False)

        st.markdown("---")
        with st.expander("📌 Como criar uma nova solicitação"):
            st.markdown("""
1. Acesse **Solicitações de Compra** no menu lateral.
2. Clique na aba **Nova Solicitação**.
3. Selecione a **Unidade Hoteleira** responsável pelo pedido.
4. Informe a **quantidade desejada** de cada produto. Produtos que não são necessários devem permanecer com quantidade zero.
5. Clique em **Enviar Solicitação**.

> A solicitação ficará com status **Aberta** até ser vinculada a uma cotação pelo comprador.
            """)

        with st.expander("📌 Como visualizar solicitações em andamento"):
            st.markdown("""
1. Acesse **Solicitações de Compra** no menu lateral.
2. Clique na aba **Solicitações Abertas**.
3. Todas as solicitações ainda não vinculadas a uma cotação serão exibidas, agrupadas por unidade.

> Solicitações já vinculadas a cotações não aparecem mais como abertas.
            """)

        with st.expander("⚠️ Pontos de atenção"):
            st.markdown("""
- Não é possível editar uma solicitação depois que ela foi vinculada a uma cotação. Se houver algum erro, entre em contato com o comprador responsável.
- Os produtos exibidos são apenas os que estão com cadastro **ativo**. Se um produto não aparecer na lista, verifique se ele está ativo no módulo de Produtos.
            """)


# ══════════════════════════════════════════════════════════════════════════════
# COTAÇÕES
# ══════════════════════════════════════════════════════════════════════════════
if "💰 Cotações" in ti:
    with ti["💰 Cotações"]:
        st.subheader("Cotações")
        st.markdown(
            "Neste módulo, o comprador agrupa as solicitações abertas e envia pedidos de "
            "cotação para os fornecedores. Cada fornecedor recebe um link exclusivo e "
            "preenche os preços sem precisar de login no sistema."
        )

        st.markdown("**Fluxo desta etapa:**")
        _h, _ht = _svg_flow(_FL_COTACOES)
        components.html(_h, height=_ht, scrolling=False)

        st.markdown("---")
        with st.expander("📌 Como criar uma cotação"):
            st.markdown("""
1. Acesse **Cotações** no menu lateral.
2. Clique na aba **Nova Cotação**.
3. Defina o **nome** da cotação para identificá-la (ex.: *Semana 40 — Alimentos*).
4. Defina a **data e hora limite** para os fornecedores responderem.
5. Selecione os **fornecedores** que serão convidados.
6. Clique em **Iniciar Cotação**.
7. O sistema exibirá um link exclusivo para cada fornecedor — copie e envie manualmente (WhatsApp, e-mail, etc.).

> Após a criação, os pedidos das solicitações bloqueadas ficam vinculados à cotação e bloqueados para edição.
            """)

        with st.expander("📌 Como acompanhar as respostas"):
            st.markdown("""
- Na aba **Em Andamento**, cada cotação aberta exibe quantos fornecedores já responderam.
- Para cada fornecedor é mostrado um ícone ✅ (respondeu) ou ⏳ (pendente), além do link para reenvio.
- Para permitir que um fornecedor **corrija** sua resposta, clique em **🔓 Liberar** — isso apaga a resposta atual e libera o preenchimento novamente.
            """)

        with st.expander("📌 Como alterar o prazo ou encerrar a cotação"):
            st.markdown("""
- **Alterar prazo:** dentro da cotação em andamento, use o formulário de alteração de prazo e clique em **Salvar prazo**.
- **Encerrar antecipadamente:** clique em **⛔ Encerrar cotação** a qualquer momento, mesmo antes do prazo.
- **Reabrir:** na aba **Encerradas**, clique em **Reabrir cotação** para permitir novas respostas.
- **Excluir** *(somente Administrador)*: na aba **Encerradas**, clique em **🗑️ Excluir** e confirme. Isso apaga a cotação, todos os links e todas as respostas vinculadas. **Esta ação não pode ser desfeita.**
            """)

        with st.expander("⚠️ Pontos de atenção"):
            st.markdown("""
- Sempre nomeie a cotação de forma descritiva — o nome aparece no PDF do pedido e facilita a identificação posterior.
- Os links gerados são de uso exclusivo de cada fornecedor. Não compartilhe o link de um fornecedor com outro.
- Uma cotação sem nenhuma resposta registrada não aparecerá na tela de Análise de Preços.
            """)


# ══════════════════════════════════════════════════════════════════════════════
# ANÁLISE DE PREÇOS
# ══════════════════════════════════════════════════════════════════════════════
if "📊 Análise de Preços" in ti:
    with ti["📊 Análise de Preços"]:
        st.subheader("Análise de Preços")
        st.markdown(
            "Após o prazo de resposta dos fornecedores, o comprador acessa este módulo para "
            "comparar preços, selecionar o fornecedor vencedor por produto e gerar os pedidos "
            "de compra. É aqui que o processo de cotação se converte em um pedido formal."
        )

        st.markdown("**Fluxo desta etapa:**")
        _h, _ht = _svg_flow(_FL_ANALISE)
        components.html(_h, height=_ht, scrolling=False)

        st.markdown("---")
        with st.expander("📌 Como analisar os preços e selecionar fornecedores"):
            st.markdown("""
1. Acesse **Análise de Preços** no menu lateral.
2. Selecione a **cotação** desejada no seletor no topo da página.
3. A grade exibe os produtos nas linhas e os fornecedores nas colunas.
4. O sistema destaca automaticamente o **menor preço** de cada produto.
5. Para selecionar um fornecedor diferente do menor preço, clique em **Selecionar** na coluna desejada.
6. Utilize o botão **Selecionar melhores preços** para marcar automaticamente o fornecedor mais barato em todos os produtos de uma vez.
            """)

        with st.expander("📌 Como ajustar quantidades por hotel"):
            st.markdown("""
- Dentro do painel de cada fornecedor, clique em **📦 Ajustar qtd.** para abrir o painel de ajuste.
- Cada linha mostra o produto e, ao lado, uma coluna por unidade hoteleira com a quantidade solicitada.
- Altere as quantidades conforme necessário e clique em **💾 Salvar quantidades**.

> Após gerar a compra, as quantidades ficam bloqueadas. Para alterar, é necessário liberar a compra (veja abaixo).
            """)

        with st.expander("📌 Pedido mínimo e como ignorar"):
            st.markdown("""
- Cada fornecedor pode ter um **pedido mínimo** cadastrado (valor total mínimo de compra).
- Se o total selecionado for inferior ao mínimo, um aviso amarelo aparece com o valor faltante por hotel.
- Para prosseguir assim mesmo, marque a caixa **Ignorar pedido mínimo** e o botão **Comprar** ficará disponível.
            """)
            st.warning(
                "⚠️ **Observação importante:** Ao ignorar o pedido mínimo, o sistema gerará o pedido "
                "normalmente. Porém, há grande probabilidade de o fornecedor não atender o pedido, pois "
                "o valor mínimo existe por razões operacionais e comerciais. Utilize esta opção apenas "
                "em situações excepcionais e com plena ciência do risco."
            )

        with st.expander("📌 Como gerar a compra"):
            st.markdown("""
1. Com os produtos selecionados e quantidades ajustadas, clique em **🛒 Comprar** no painel do fornecedor.
2. O sistema gera os pedidos e exibe a mensagem de confirmação.
3. O botão **⬇️ Gerar PDF** fica disponível — baixe o arquivo, abra no navegador e use **Ctrl+P → Salvar como PDF**.
4. Envie o PDF ao fornecedor pelo meio de sua preferência (e-mail, WhatsApp, etc.).
            """)

        with st.expander("📌 Como liberar para uma nova compra"):
            st.markdown("""
Se for necessário desfazer uma compra já gerada e refazer (por exemplo, para corrigir quantidades):

1. Clique em **🔓 Liberar para nova compra**.
2. Digite a sua **senha de acesso** no campo que aparece e clique em **Confirmar**.
3. O pedido anterior é **excluído automaticamente** do banco de dados para evitar duplicatas.
4. O botão **Comprar** retorna e o processo pode ser feito novamente.

> **Atenção:** esta ação remove o pedido anterior de forma permanente. Certifique-se de que o PDF já foi salvo antes de liberar, caso ainda precise dele.
            """)

        with st.expander("⚠️ Pontos de atenção"):
            st.markdown("""
- Um produto pode ser comprado de **apenas um fornecedor por cotação** — é a seleção que define isso.
- O estado "compra gerada" é preservado mesmo que a página seja atualizada ou o cache seja limpo, pois as informações ficam salvas no banco de dados.
- A tela de Análise só exibe cotações que têm ao menos uma resposta de fornecedor registrada.
            """)


# ══════════════════════════════════════════════════════════════════════════════
# ORDEM DE COMPRA
# ══════════════════════════════════════════════════════════════════════════════
if "🛒 Ordem de Compra" in ti:
    with ti["🛒 Ordem de Compra"]:
        st.subheader("Ordem de Compra")
        st.markdown(
            "Nesta tela ficam listados todos os pedidos gerados que ainda não foram enviados "
            "aos fornecedores. Os pedidos são agrupados por fornecedor e o comprador pode "
            "baixar o PDF, marcar como enviado ou excluir."
        )

        st.markdown("**Fluxo desta etapa:**")
        _h, _ht = _svg_flow(_FL_ORDEM)
        components.html(_h, height=_ht, scrolling=False)

        st.markdown("---")
        with st.expander("📌 Como baixar e imprimir o pedido"):
            st.markdown("""
1. Acesse **Ordem de Compra** no menu lateral.
2. Clique no expander do fornecedor desejado para expandir o pedido.
3. Clique em **⬇️ Baixar pedido (imprimir / salvar PDF)**.
4. Abra o arquivo `.html` baixado em qualquer navegador.
5. Use o atalho **Ctrl+P** (ou Cmd+P no Mac) e selecione **Salvar como PDF**.
6. O PDF contém os dados de todas as unidades hoteleiras que compraram deste fornecedor nesta cotação.
            """)

        with st.expander("📌 Como marcar o pedido como enviado"):
            st.markdown("""
- Após enviar o PDF ao fornecedor, clique em **✅ Marcar tudo como enviado**.
- Isso marca **todas as compras do grupo** (todas as unidades daquele fornecedor) como enviadas de uma vez.
- O pedido sai da lista de pendentes e não aparece mais nesta tela.

> Pedidos marcados como enviados podem ser consultados nos **Relatórios**.
            """)

        with st.expander("📌 Como deletar um pedido"):
            st.markdown("""
- Clique em **🗑️ Deletar pedido** para remover permanentemente o pedido e todos os seus itens do banco de dados.
- Use esta opção com cautela — a ação não pode ser desfeita.
- Se o objetivo é corrigir valores ou quantidades, utilize a opção **Liberar para nova compra** na tela de Análise de Preços.
            """)

        with st.expander("⚠️ Pontos de atenção"):
            st.markdown("""
- Esta tela exibe apenas pedidos **pendentes de envio**. Pedidos já marcados como enviados não aparecem aqui.
- O PDF inclui: número do pedido, nome da cotação, data, dados do comprador (unidade hoteleira), dados do fornecedor, tabela de itens com gramatura solicitada, gramatura informada, marca, observação, preço unitário, quantidade e total.
- O total geral de todas as unidades daquele fornecedor é exibido ao final do PDF.
            """)


# ══════════════════════════════════════════════════════════════════════════════
# RECEBIMENTO
# ══════════════════════════════════════════════════════════════════════════════
if "📥 Recebimento" in ti:
    with ti["📥 Recebimento"]:
        st.subheader("Recebimento de NF-e")
        st.markdown(
            "Este módulo permite registrar o recebimento de mercadorias através do upload "
            "do arquivo XML da nota fiscal eletrônica (NF-e). O sistema lê os dados da nota "
            "automaticamente e vincula ao fornecedor cadastrado pelo CNPJ."
        )

        st.markdown("**Fluxo desta etapa:**")
        _h, _ht = _svg_flow(_FL_RECEBIMENTO)
        components.html(_h, height=_ht, scrolling=False)

        st.markdown("---")
        with st.expander("📌 Como registrar um recebimento"):
            st.markdown("""
1. Acesse **Recebimento NF-e** no menu lateral.
2. Faça o upload do arquivo **XML da NF-e** recebida do fornecedor.
3. O sistema lê automaticamente os dados da nota: fornecedor, itens, quantidades e valores.
4. Confirme os itens recebidos e as quantidades.
5. Salve o registro — os dados ficam disponíveis para consulta nos Relatórios.
            """)

        with st.expander("⚠️ Pontos de atenção"):
            st.markdown("""
- O arquivo deve ser o **XML original da NF-e**, não o PDF impresso (DANFE).
- O sistema identifica o fornecedor automaticamente pelo CNPJ constante na nota.
- Se o CNPJ do fornecedor não estiver cadastrado no sistema, o recebimento pode não ser vinculado corretamente — cadastre o fornecedor antes de registrar o recebimento.
            """)


# ══════════════════════════════════════════════════════════════════════════════
# COMPRA AVULSA
# ══════════════════════════════════════════════════════════════════════════════
if "🧾 Compra Avulsa" in ti:
    with ti["🧾 Compra Avulsa"]:
        st.subheader("Compra Avulsa")
        st.markdown(
            "Utilize este módulo para registrar compras realizadas **fora do processo normal** "
            "de cotação — como compras emergenciais ou de produtos adquiridos diretamente "
            "sem cotação prévia. O registro é feito pelo upload do XML da nota fiscal."
        )

        st.markdown("**Fluxo desta etapa:**")
        _h, _ht = _svg_flow(_FL_AVULSA)
        components.html(_h, height=_ht, scrolling=False)

        st.markdown("---")
        with st.expander("📌 Como registrar uma compra avulsa"):
            st.markdown("""
1. Acesse **Compra Avulsa** no menu lateral.
2. Faça o upload do arquivo **XML da NF-e** da compra realizada.
3. O sistema lê os dados da nota e exibe os itens.
4. Confirme e salve — os dados ficam registrados no histórico para consulta nos Relatórios.
            """)

        with st.expander("⚠️ Quando utilizar"):
            st.markdown("""
- Compras emergenciais realizadas diretamente com o fornecedor, sem cotação prévia.
- Compras de produtos que ainda não estão cadastrados no sistema.
- Notas de fornecedores que não participaram de cotações.

> Para compras dentro do processo normal (com cotação), utilize o fluxo completo: **Análise de Preços → Ordem de Compra → Recebimento NF-e**.
            """)


# ══════════════════════════════════════════════════════════════════════════════
# CADASTROS
# ══════════════════════════════════════════════════════════════════════════════
if "📦 Cadastros" in ti:
    with ti["📦 Cadastros"]:
        st.subheader("Cadastros")
        st.markdown(
            "Os cadastros são a base de funcionamento do sistema. Sem produtos e fornecedores "
            "cadastrados, não é possível criar solicitações ou cotações. Mantenha os cadastros "
            "sempre atualizados para garantir o bom funcionamento de todo o processo."
        )

        if "produtos" in perm:
            st.markdown("### 📦 Produtos")
            with st.expander("📌 Como cadastrar um produto"):
                st.markdown("""
1. Acesse **Produtos** no menu lateral.
2. Clique em **Novo Produto**.
3. Preencha os campos:
   - **Descrição** — nome do produto como será exibido no sistema e nos PDFs.
   - **Código** — código interno (opcional, para identificação).
   - **Apresentação** — gramatura padrão do produto (ex.: *Pacote 500g*, *Caixa 12 un*). Esta é a gramatura solicitada que aparecerá no pedido de compra.
   - **Unidade Base** — a unidade de medida da apresentação (ex.: kg, lt, un).
   - **Observação** — informações adicionais sobre o produto (opcional, visível nas solicitações).
   - **Ativo** — mantenha marcado para que o produto apareça nas solicitações.
4. Salve o produto.
                """)
            with st.expander("⚠️ Pontos de atenção"):
                st.markdown("""
- Produtos **inativos** não aparecem na tela de Solicitações de Compra.
- A **Apresentação** é o que o fornecedor verá como referência ao cotar — descreva com clareza (ex.: *Fardo 5kg*, *Pacote 500g*).
- O campo **Gramatura Solicitada** no PDF vem diretamente deste campo de Apresentação.
                """)

        if "fornecedores" in perm:
            st.markdown("### 🏭 Fornecedores")
            with st.expander("📌 Como cadastrar um fornecedor"):
                st.markdown("""
1. Acesse **Fornecedores** no menu lateral.
2. Clique em **Novo Fornecedor**.
3. Preencha os campos:
   - **Razão Social** e **Nome Fantasia** — nome oficial e nome comercial.
   - **CNPJ** — utilizado para identificação no recebimento de NF-e.
   - **Telefone / WhatsApp** — contato para envio manual dos pedidos.
   - **Pedido Mínimo (R$)** — valor mínimo de compra aceito pelo fornecedor. O sistema alertará quando o total estiver abaixo deste valor.
   - **Endereço completo** — aparece no cabeçalho do PDF do pedido.
   - **Ativo** — mantenha marcado para que o fornecedor apareça nas cotações.
4. Salve o fornecedor.
                """)
            with st.expander("⚠️ Pontos de atenção"):
                st.markdown("""
- O **CNPJ** é fundamental para o correto funcionamento do recebimento de NF-e.
- Fornecedores **inativos** não aparecem na criação de novas cotações.
- O **Pedido Mínimo** é apenas um aviso — é possível ignorá-lo na Análise de Preços, mas há grande risco de o fornecedor não atender o pedido (consulte a aba Análise de Preços para mais detalhes).
                """)


# ══════════════════════════════════════════════════════════════════════════════
# RELATÓRIOS
# ══════════════════════════════════════════════════════════════════════════════
if "📈 Relatórios" in ti:
    with ti["📈 Relatórios"]:
        st.subheader("Relatórios e Análises")
        st.markdown(
            "O módulo de Relatórios oferece visões analíticas sobre as compras realizadas, "
            "evolução de preços e desempenho dos fornecedores ao longo do tempo."
        )
        with st.expander("📌 Relatórios disponíveis"):
            st.markdown("""
- **Compras por Período** — total de compras realizadas em um intervalo de datas, agrupadas por fornecedor ou produto.
- **Evolução de Preços** — histórico de preços de um produto específico ao longo do tempo, por fornecedor.
- **Consumo por Produto** — quantidade total comprada de cada produto no período selecionado.
- **Desempenho de Fornecedores** — quantas vezes cada fornecedor ganhou cotações e comparativo de preços.
- **Orçamento vs. Gasto** — comparativo entre o orçamento definido por unidade/mês e o valor efetivamente gasto.
            """)
        with st.expander("⚠️ Pontos de atenção"):
            st.markdown("""
- Os relatórios são gerados com base nas compras já realizadas e marcadas como enviadas.
- Para que o relatório de **Orçamento vs. Gasto** funcione, é necessário cadastrar os orçamentos mensais em **Configurações → Orçamentos**.
- O histórico de preços é registrado automaticamente a cada compra gerada.
            """)


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES
# ══════════════════════════════════════════════════════════════════════════════
if "⚙️ Configurações" in ti:
    with ti["⚙️ Configurações"]:
        st.subheader("Configurações")
        st.markdown(
            "Área exclusiva do perfil **Administrador**. Reúne o gerenciamento de unidades "
            "hoteleiras, unidades de medida, usuários, orçamentos e backup dos dados."
        )

        with st.expander("📌 Unidades Hoteleiras"):
            st.markdown("""
Cadastro de cada hotel ou unidade que faz pedidos de compra.

- **Campos:** Nome (Razão Social), Nome Fantasia, CNPJ, CEP e endereço completo.
- O Nome Fantasia é o que aparece nas telas e nos PDFs como identificação do comprador.
- O CNPJ aparece no cabeçalho "Comprador" do PDF de pedido.
- Unidades podem ser marcadas como **inativas** para que não apareçam nas solicitações.
            """)

        with st.expander("📌 Unidades de Medida"):
            st.markdown("""
Define as opções de tipo de embalagem que os fornecedores podem selecionar ao cotar.

- **Campos:** Sigla (ex.: kg, lt, un) e Nome Completo (ex.: Quilograma, Litro, Unidade).
- Somente unidades **ativas** aparecem no formulário de cotação do fornecedor.
- Adicione novas unidades conforme necessário — elas aparecem automaticamente no formulário público.
            """)

        with st.expander("📌 Usuários"):
            st.markdown("""
Gerenciamento de quem acessa o sistema.

- **Perfis disponíveis:** Digitador, Comprador, Administrador.
- Para cada usuário é possível definir **permissões individuais** — quais módulos pode acessar — independentemente do perfil base.
- Novos usuários recebem uma senha temporária e são obrigados a trocá-la no primeiro acesso.
- Usuários **inativos** não conseguem fazer login.
- **Unidades de acesso:** define a quais unidades hoteleiras o usuário tem acesso (útil para digitadores que atuam em unidades específicas).
            """)

        with st.expander("📌 Orçamentos"):
            st.markdown("""
Define o valor de orçamento mensal por unidade hoteleira.

- Informado em reais (R$) por unidade e por mês/ano.
- Utilizado no relatório **Orçamento vs. Gasto** para mostrar se as compras estão dentro do previsto.
            """)

        with st.expander("📌 Backup / Exportar"):
            st.markdown("""
Permite exportar os dados do sistema para backup externo ou análise.

- **Exportar para Google Sheets** — copia todos os dados do banco de dados PostgreSQL para a planilha de backup.
- **Exportar como Excel** — gera um arquivo .xlsx com todas as tabelas do sistema para guardar localmente.
- **Importar de Excel** — restaura os dados a partir de um arquivo de backup (sobrescreve os dados atuais).

> Recomenda-se realizar backups periódicos, especialmente antes de alterações em massa ou atualizações do sistema.
            """)


# ══════════════════════════════════════════════════════════════════════════════
# MINHA CONTA
# ══════════════════════════════════════════════════════════════════════════════
with ti["🔑 Minha Conta"]:
    st.subheader("Minha Conta")
    st.markdown("Configurações relacionadas à sua própria conta de acesso.")

    with st.expander("📌 Como alterar a sua senha"):
        st.markdown("""
1. Acesse **Alterar Senha** no menu lateral.
2. Informe a **nova senha** desejada e confirme-a no campo seguinte.
3. A senha deve ter entre **6 e 72 caracteres**.
4. Clique em **Salvar nova senha**.

> Após salvar, a nova senha entra em vigor imediatamente no próximo acesso.
        """)

    with st.expander("📌 Primeiro acesso"):
        st.markdown("""
- Ao receber um usuário novo, o sistema exige a troca de senha antes de liberar o acesso às demais telas.
- Escolha uma senha segura que apenas você conhece.
- Em caso de dúvidas ou problemas de acesso, entre em contato com o administrador do sistema.
        """)

    with st.expander("⚠️ Segurança"):
        st.markdown("""
- Não compartilhe sua senha com outras pessoas.
- Sua senha é utilizada para confirmar ações sensíveis no sistema, como **liberar uma compra** para refazer.
- Caso suspeite que sua senha foi comprometida, troque-a imediatamente em **Alterar Senha**.
        """)
