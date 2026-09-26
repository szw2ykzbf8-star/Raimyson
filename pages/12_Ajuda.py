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
    "Aqui você encontra orientações detalhadas sobre como utilizar cada módulo do sistema, "
    "além de fluxogramas visuais que explicam o passo a passo de cada processo."
)
st.markdown("---")

# ── Fluxograma HTML ───────────────────────────────────────────────────────────
_FLOW_CSS = """
<style>
  body { font-family: Arial, sans-serif; margin: 0; padding: 8px; }
  .flow-wrap { max-width: 680px; margin: auto; }
  .fstep {
    background: #1565C0; color: #fff; border-radius: 10px;
    padding: 12px 18px; cursor: pointer; user-select: none;
    display: flex; align-items: center; gap: 12px; margin-bottom: 2px;
    box-shadow: 0 2px 4px rgba(0,0,0,.15); transition: background .2s;
  }
  .fstep:hover { background: #0D47A1; }
  .fstep.green  { background: #2E7D32; }
  .fstep.green:hover  { background: #1B5E20; }
  .fstep.purple { background: #6A1B9A; }
  .fstep.purple:hover { background: #4A148C; }
  .fstep.orange { background: #E65100; }
  .fstep.orange:hover { background: #BF360C; }
  .fstep.teal   { background: #00695C; }
  .fstep.teal:hover   { background: #004D40; }
  .fstep.gray   { background: #546E7A; }
  .fstep.gray:hover   { background: #37474F; }
  .fnum {
    background: rgba(255,255,255,.25); border-radius: 50%;
    min-width: 28px; height: 28px; display: flex; align-items: center;
    justify-content: center; font-weight: bold; font-size: 13px;
  }
  .ftitle { font-weight: bold; font-size: 14px; flex: 1; }
  .fchev { font-size: 12px; transition: transform .2s; }
  .fchev.open { transform: rotate(180deg); }
  .fdetail {
    display: none; background: #F3F6FB; border-left: 4px solid #1565C0;
    border-radius: 0 0 8px 8px; padding: 12px 16px; font-size: 13px;
    color: #222; line-height: 1.7; margin-bottom: 2px;
  }
  .fdetail.green  { border-color: #2E7D32; }
  .fdetail.purple { border-color: #6A1B9A; }
  .fdetail.orange { border-color: #E65100; }
  .fdetail.teal   { border-color: #00695C; }
  .fdetail.gray   { border-color: #546E7A; }
  .fdetail ul { margin: 6px 0 6px 18px; padding: 0; }
  .fdetail li { margin-bottom: 4px; }
  .farrow { text-align: center; color: #90A4AE; font-size: 22px; margin: 0; line-height: 1.2; }
  .ftag {
    display: inline-block; background: rgba(255,255,255,.2);
    border-radius: 4px; font-size: 11px; padding: 1px 7px; margin-left: 6px;
  }
</style>
<script>
function ftoggle(id) {
  var d = document.getElementById('fd_' + id);
  var c = document.getElementById('fc_' + id);
  if (d.style.display === 'block') {
    d.style.display = 'none'; c.classList.remove('open');
  } else {
    d.style.display = 'block'; c.classList.add('open');
  }
}
</script>
"""

def _step(n, cor, titulo, tag, conteudo_html):
    return f"""
<div class="fstep {cor}" onclick="ftoggle('{n}')">
  <div class="fnum">{n}</div>
  <div class="ftitle">{titulo}<span class="ftag">{tag}</span></div>
  <div class="fchev" id="fc_{n}">▼</div>
</div>
<div class="fdetail {cor}" id="fd_{n}">{conteudo_html}</div>
"""

def _arrow():
    return '<div class="farrow">↓</div>'

def fluxo_geral():
    html = _FLOW_CSS + '<div class="flow-wrap">'
    html += _step("1","gray","Cadastros Iniciais","Pré-requisito","""
      <p>Antes de iniciar qualquer processo de compra, os dados base precisam estar cadastrados:</p>
      <ul>
        <li><b>Unidades de Medida</b> — as gramaturas/embalagens disponíveis (ex.: kg, lt, un).</li>
        <li><b>Produtos</b> — tudo que pode ser comprado, com descrição, apresentação e unidade base.</li>
        <li><b>Fornecedores</b> — empresas que vendem os produtos, com CNPJ, contato e pedido mínimo.</li>
        <li><b>Unidades Hoteleiras</b> — os hotéis/unidades que fazem pedidos.</li>
        <li><b>Usuários</b> — as pessoas que acessam o sistema e seus perfis de permissão.</li>
      </ul>
      <p>Esses cadastros ficam disponíveis nos menus <b>Produtos</b>, <b>Fornecedores</b> e <b>Configurações</b>.</p>
    """)
    html += _arrow()
    html += _step("2","","Solicitação de Compra","Digitador / Comprador","""
      <p>Cada unidade hoteleira registra o que precisa comprar:</p>
      <ul>
        <li>O responsável acessa <b>Solicitações de Compra</b> e informa a quantidade de cada produto.</li>
        <li>Podem existir várias solicitações abertas ao mesmo tempo — uma por unidade.</li>
        <li>Uma solicitação é <b>vinculada a uma cotação</b> quando o comprador cria a cotação.</li>
        <li>Após o vínculo, a solicitação fica bloqueada para edição.</li>
      </ul>
      <p><b>Importante:</b> o digitador só vê o módulo de Solicitações. O restante do processo é feito pelo comprador ou administrador.</p>
    """)
    html += _arrow()
    html += _step("3","purple","Criação da Cotação","Comprador / Admin","""
      <p>O comprador agrupa as solicitações abertas em uma cotação e envia para os fornecedores:</p>
      <ul>
        <li>Define um <b>nome</b> para identificar a cotação (ex.: Semana 40 — Hotel Centro).</li>
        <li>Define o <b>prazo limite</b> para os fornecedores responderem.</li>
        <li>Seleciona quais <b>solicitações abertas</b> farão parte desta cotação.</li>
        <li>Seleciona os <b>fornecedores</b> que serão convidados a cotar.</li>
        <li>O sistema gera um <b>link exclusivo</b> para cada fornecedor — cada um só enxerga os próprios dados.</li>
        <li>O comprador envia os links manualmente (WhatsApp, e-mail ou outro meio).</li>
      </ul>
    """)
    html += _arrow()
    html += _step("4","orange","Resposta do Fornecedor","Fornecedor (link público)","""
      <p>O fornecedor acessa o link recebido e preenche os preços — sem precisar de login no sistema:</p>
      <ul>
        <li>Informa o <b>preço por embalagem</b> de cada produto que fornece.</li>
        <li>Informa o <b>tipo de embalagem</b> (kg, lt, un…) e a <b>quantidade por embalagem</b>.</li>
        <li>Informa a <b>marca</b> (campo obrigatório) e uma observação opcional.</li>
        <li>Produtos que o fornecedor não trabalha devem ter preço zero.</li>
        <li>Após enviar, <b>não é possível alterar</b> — para mudanças, o fornecedor deve contatar o comprador.</li>
        <li>O link expira automaticamente no prazo definido na cotação.</li>
      </ul>
    """)
    html += _arrow()
    html += _step("5","green","Análise de Preços","Comprador / Admin","""
      <p>O comprador compara todos os preços recebidos e decide de quem vai comprar cada produto:</p>
      <ul>
        <li>A grade mostra todos os fornecedores e seus preços por produto.</li>
        <li>O sistema destaca automaticamente o <b>menor preço</b> de cada item.</li>
        <li>O comprador pode escolher outro fornecedor clicando no botão de seleção da coluna correspondente.</li>
        <li>É possível <b>ajustar as quantidades</b> por hotel dentro de cada fornecedor (expander "Ajustar qtd.").</li>
        <li>Se o total de um fornecedor não atingir o <b>pedido mínimo</b>, um aviso é exibido — marque <b>"Ignorar pedido mínimo"</b> para prosseguir assim mesmo.</li>
        <li>Ao clicar em <b>Comprar</b>, o pedido é gerado e o PDF fica disponível para download.</li>
        <li>Para desfazer uma compra já gerada, clique em <b>"Liberar para nova compra"</b> e confirme com a senha — o pedido anterior é <b>excluído automaticamente</b>.</li>
      </ul>
    """)
    html += _arrow()
    html += _step("6","teal","Pedido de Compra (PDF)","Comprador / Admin","""
      <p>Os pedidos gerados ficam disponíveis na tela <b>Ordem de Compra</b>:</p>
      <ul>
        <li>Os pedidos são agrupados por fornecedor.</li>
        <li>O comprador baixa o <b>PDF</b> clicando em "Baixar pedido" e abre no navegador para imprimir ou salvar.</li>
        <li>Após enviar o PDF ao fornecedor, clica em <b>"Marcar tudo como enviado"</b> — o pedido sai da lista de pendentes.</li>
        <li>Se necessário, é possível <b>deletar</b> o pedido inteiro do fornecedor.</li>
      </ul>
    """)
    html += _arrow()
    html += _step("7","gray","Recebimento da Mercadoria","Comprador / Admin","""
      <p>Quando a mercadoria chega, o comprador pode registrar o recebimento:</p>
      <ul>
        <li>Acesse <b>Recebimento NF-e</b> e faça o upload do arquivo XML da nota fiscal.</li>
        <li>O sistema identifica automaticamente o fornecedor pelo CNPJ.</li>
        <li>Os itens da nota são comparados com os produtos cadastrados.</li>
        <li>O comprador confirma as quantidades recebidas.</li>
        <li>As informações ficam registradas para consulta futura nos Relatórios.</li>
      </ul>
      <p>Compras realizadas fora do sistema (sem cotação) podem ser importadas via <b>Compra Avulsa</b>, também por upload de XML.</p>
    """)
    html += '</div>'
    return html


# ── Tabs ──────────────────────────────────────────────────────────────────────
tabs_nomes = ["🗺️ Visão Geral"]
if "pedidos"       in perm: tabs_nomes.append("📋 Solicitações")
if "cotacoes"      in perm: tabs_nomes.append("💰 Cotações")
if "analise"       in perm: tabs_nomes.append("📊 Análise de Preços")
if "ordem"         in perm: tabs_nomes.append("🛒 Ordem de Compra")
if "recebimento"   in perm: tabs_nomes.append("📥 Recebimento")
if "compra_avulsa" in perm: tabs_nomes.append("🧾 Compra Avulsa")
if "produtos"      in perm or "fornecedores" in perm: tabs_nomes.append("📦 Cadastros")
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
        "unidade hoteleira até o recebimento da mercadoria. Clique em cada etapa abaixo para ver "
        "os detalhes."
    )
    components.html(fluxo_geral(), height=560, scrolling=True)

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
# SOLICITAÇÕES DE COMPRA
# ══════════════════════════════════════════════════════════════════════════════
if "📋 Solicitações" in ti:
    with ti["📋 Solicitações"]:
        st.subheader("Solicitações de Compra")
        st.markdown(
            "Este módulo é o ponto de partida do processo. É aqui que cada unidade hoteleira "
            "registra os produtos que precisa comprar antes que uma cotação seja gerada."
        )

        with st.expander("📌 Como criar uma nova solicitação"):
            st.markdown("""
1. Acesse **Solicitações de Compra** no menu lateral.
2. Clique na aba **Nova Solicitação**.
3. Selecione a **Unidade Hoteleira** responsável pelo pedido.
4. Informe a **quantidade desejada** de cada produto. Produtos que não são necessários devem ficar com quantidade zero.
5. Clique em **Salvar Solicitação**.

> A solicitação ficará com status **Aberta** até ser vinculada a uma cotação.
            """)

        with st.expander("📌 Como visualizar solicitações em andamento"):
            st.markdown("""
1. Acesse **Solicitações de Compra** no menu lateral.
2. Clique na aba **Solicitações Abertas**.
3. Todas as solicitações ainda não vinculadas a uma cotação serão exibidas, agrupadas por unidade.

> Solicitações vinculadas a cotações não aparecem mais como abertas.
            """)

        with st.expander("⚠️ Pontos de atenção"):
            st.markdown("""
- Não é possível editar uma solicitação depois que ela foi vinculada a uma cotação. Se houver algum erro, entre em contato com o comprador responsável.
- Uma mesma unidade pode ter apenas uma solicitação aberta por vez. Caso já exista uma aberta, ela aparecerá na aba **Solicitações Abertas** para edição.
- Os produtos exibidos são apenas os que estão com cadastro **ativo**. Se um produto não aparecer na lista, verifique se ele está ativo no cadastro de Produtos.
            """)

        st.markdown("---")
        st.markdown("**Fluxo desta etapa:**")
        _fl = _FLOW_CSS + '<div class="flow-wrap">'
        _fl += _step("A","","Acessar Solicitações de Compra","Menu lateral","""<ul><li>Clique em <b>Solicitações de Compra</b> no menu.</li></ul>""")
        _fl += _arrow()
        _fl += _step("B","purple","Selecionar unidade hoteleira","Aba: Nova Solicitação","""<ul><li>Escolha o hotel/unidade no seletor de unidade.</li></ul>""")
        _fl += _arrow()
        _fl += _step("C","orange","Preencher quantidades","Lista de produtos","""<ul><li>Informe a quantidade de cada item necessário.</li><li>Deixe em zero os que não precisar.</li></ul>""")
        _fl += _arrow()
        _fl += _step("D","green","Salvar solicitação","Botão: Salvar Solicitação","""<ul><li>A solicitação fica disponível para o comprador vincular a uma cotação.</li></ul>""")
        _fl += '</div>'
        components.html(_fl, height=280, scrolling=False)


# ══════════════════════════════════════════════════════════════════════════════
# COTAÇÕES
# ══════════════════════════════════════════════════════════════════════════════
if "💰 Cotações" in ti:
    with ti["💰 Cotações"]:
        st.subheader("Cotações")
        st.markdown(
            "Neste módulo, o comprador agrupa as solicitações abertas e envia os pedidos de "
            "cotação para os fornecedores, cada um por meio de um link exclusivo."
        )

        with st.expander("📌 Como criar uma cotação"):
            st.markdown("""
1. Acesse **Cotações** no menu lateral.
2. Clique na aba **Nova Cotação**.
3. Defina o **nome** da cotação para identificá-la (ex.: *Semana 40 — Alimentos*)
4. Defina a **data e hora limite** para os fornecedores responderem.
5. Selecione as **solicitações abertas** que farão parte desta cotação.
6. Selecione os **fornecedores** que serão convidados.
7. Clique em **Criar Cotação e Gerar Links**.
8. O sistema exibirá um link exclusivo para cada fornecedor — copie e envie manualmente (WhatsApp, e-mail, etc.).

> Após a criação, os produtos das solicitações selecionadas ficam agrupados e os totais por unidade são calculados automaticamente.
            """)

        with st.expander("📌 Como reabrir ou encerrar uma cotação"):
            st.markdown("""
- **Encerrar:** uma cotação é encerrada automaticamente quando o prazo limite é atingido. Também pode ser encerrada manualmente.
- **Reabrir:** na aba **Encerradas**, clique em **Reabrir cotação** para permitir novas respostas. O prazo deve ser ajustado para uma data futura se necessário.
- **Excluir** *(somente Administrador)*: na aba **Encerradas**, clique em **🗑️ Excluir** e confirme. Isso apaga a cotação, todos os tokens de acesso e todas as respostas dos fornecedores vinculados a ela. **Esta ação não pode ser desfeita.**
            """)

        with st.expander("📌 Como o fornecedor acessa a cotação"):
            st.markdown("""
- Cada fornecedor recebe um **link único** que abre um formulário público no navegador — sem necessidade de criar conta ou fazer login.
- O formulário exibe apenas os produtos desta cotação e os campos de preço, embalagem, marca e observação.
- Após enviar, o fornecedor **não consegue alterar** as respostas. Para correções, deve entrar em contato com o comprador.
- O link expira automaticamente na data e hora definidas no prazo da cotação.
            """)

        with st.expander("⚠️ Pontos de atenção"):
            st.markdown("""
- Sempre que possível, nomeie a cotação de forma descritiva — o nome aparece no PDF do pedido e facilita a identificação posterior.
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
            "comparar preços, selecionar vencedores por produto e gerar os pedidos de compra."
        )

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
- Dentro do painel de cada fornecedor, clique em **📦 Ajustar qtd.** para abrir o expander de ajuste.
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

        with st.expander("📌 Como gerar a compra"):
            st.markdown("""
1. Com os produtos selecionados e quantidades ajustadas, clique em **🛒 Comprar** no painel do fornecedor.
2. O sistema gera os pedidos no banco de dados e exibe a mensagem de confirmação.
3. O botão **⬇️ Gerar PDF** fica disponível — baixe o arquivo, abra no navegador e use **Ctrl+P → Salvar como PDF** para gerar o arquivo definitivo.
4. Envie o PDF ao fornecedor pelo meio de sua preferência (e-mail, WhatsApp, etc.).
            """)

        with st.expander("📌 Como liberar para uma nova compra"):
            st.markdown("""
Se for necessário desfazer uma compra já gerada e refazer (por exemplo, para corrigir quantidades):

1. Clique em **🔓 Liberar para nova compra**.
2. Digite a sua **senha de acesso** no campo que aparece e clique em **Confirmar**.
3. O pedido anterior é **excluído automaticamente** do banco de dados para evitar duplicatas.
4. O botão **Comprar** retorna e o processo pode ser feito novamente.

> **Atenção:** esta ação remove o pedido anterior permanentemente. Certifique-se de que o PDF já foi salvo antes de liberar, caso ainda precise dele.
            """)

        with st.expander("⚠️ Pontos de atenção"):
            st.markdown("""
- Um produto pode ser comprado de **apenas um fornecedor por cotação** — é a seleção que define isso.
- O estado "compra gerada" é preservado mesmo que a página seja atualizada ou o cache seja limpo, pois as informações ficam salvas no banco de dados.
- A tela de Análise só exibe cotações que têm ao menos uma resposta de fornecedor.
            """)


# ══════════════════════════════════════════════════════════════════════════════
# ORDEM DE COMPRA
# ══════════════════════════════════════════════════════════════════════════════
if "🛒 Ordem de Compra" in ti:
    with ti["🛒 Ordem de Compra"]:
        st.subheader("Ordem de Compra")
        st.markdown(
            "Nesta tela ficam listados todos os pedidos gerados que ainda não foram enviados "
            "aos fornecedores. Os pedidos são agrupados por fornecedor."
        )

        with st.expander("📌 Como baixar e imprimir o pedido"):
            st.markdown("""
1. Acesse **Ordem de Compra** no menu lateral.
2. Clique no expander do fornecedor desejado para expandir o pedido.
3. Clique em **⬇️ Baixar pedido (imprimir / salvar PDF)**.
4. Abra o arquivo `.html` baixado em qualquer navegador.
5. Use o atalho **Ctrl+P** (ou Cmd+P no Mac) e selecione **Salvar como PDF** para gerar o arquivo definitivo.
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
- O PDF inclui: número do pedido, nome da cotação, data, dados do comprador (unidade hoteleira), dados do fornecedor, tabela de itens com gramatura solicitada, gramatura informada pelo fornecedor, marca, observação, preço unitário, quantidade e total.
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
            "do arquivo XML da nota fiscal eletrônica (NF-e)."
        )

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
- O arquivo deve ser o XML original da NF-e, não o PDF (DANFE).
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
            "de cotação — como compras emergenciais ou de produtos não cadastrados no sistema."
        )

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

> Para compras dentro do processo normal (com cotação), utilize o fluxo completo: Análise → Ordem de Compra → Recebimento NF-e.
            """)


# ══════════════════════════════════════════════════════════════════════════════
# CADASTROS
# ══════════════════════════════════════════════════════════════════════════════
if "📦 Cadastros" in ti:
    with ti["📦 Cadastros"]:
        st.subheader("Cadastros")
        st.markdown(
            "Os cadastros são a base de funcionamento do sistema. Sem produtos e fornecedores "
            "cadastrados, não é possível criar solicitações ou cotações."
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
   - **Apresentação** — gramatura padrão do produto (ex.: *Pacote 500g*, *Caixa 12 un*). Esta é a gramatura solicitada que aparecerá no pedido.
   - **Unidade Base** — a unidade de medida da apresentação (ex.: kg, lt, un).
   - **Qtd. Base por Apresentação** — quantas unidades base cabem em uma apresentação (ex.: caixa com 12 unidades → informar 12).
   - **Observação** — informações adicionais sobre o produto (opcional).
   - **Ativo** — mantenha marcado para que o produto apareça nas solicitações.
4. Salve o produto.
                """)
            with st.expander("⚠️ Pontos de atenção"):
                st.markdown("""
- Produtos inativos não aparecem na tela de Solicitações de Compra.
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
   - **Endereço** (CEP, logradouro, número, etc.) — aparece no PDF do pedido.
   - **Ativo** — mantenha marcado para que o fornecedor apareça nas cotações.
4. Salve o fornecedor.
                """)
            with st.expander("⚠️ Pontos de atenção"):
                st.markdown("""
- O CNPJ é fundamental para o correto funcionamento do recebimento de NF-e.
- Fornecedores inativos não aparecem na criação de cotações.
- O **Pedido Mínimo** é apenas um aviso — é possível ignorá-lo na Análise de Preços marcando "Ignorar pedido mínimo".
                """)


# ══════════════════════════════════════════════════════════════════════════════
# RELATÓRIOS
# ══════════════════════════════════════════════════════════════════════════════
if "📈 Relatórios" in ti:
    with ti["📈 Relatórios"]:
        st.subheader("Relatórios e Análises")
        st.markdown(
            "O módulo de Relatórios oferece visões analíticas sobre as compras realizadas, "
            "evolução de preços e desempenho dos fornecedores."
        )
        with st.expander("📌 Relatórios disponíveis"):
            st.markdown("""
- **Compras por Período** — total de compras realizadas em um intervalo de datas, agrupadas por fornecedor ou produto.
- **Evolução de Preços** — histórico de preços de um produto específico ao longo do tempo, por fornecedor.
- **Consumo por Produto** — quantidade total comprada de cada produto no período selecionado.
- **Desempenho de Fornecedores** — quantas vezes cada fornecedor ganhou cotações, percentual de participação e comparativo de preços.
- **Orçamento vs. Gasto** — comparativo entre o orçamento definido por unidade/mês e o valor efetivamente gasto.
            """)
        with st.expander("⚠️ Pontos de atenção"):
            st.markdown("""
- Os relatórios são gerados com base nas compras já realizadas e marcadas como enviadas.
- Para que o relatório de Orçamento vs. Gasto funcione, é necessário cadastrar os orçamentos mensais em **Configurações → Orçamentos**.
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
- O Nome Fantasia é o que aparece nas telas e nos PDFs.
- O CNPJ aparece no cabeçalho "Comprador" do PDF de pedido.
- Unidades podem ser marcadas como **inativas** para que não apareçam nas solicitações.
            """)

        with st.expander("📌 Unidades de Medida"):
            st.markdown("""
Define as opções de tipo de embalagem que os fornecedores podem selecionar ao cotar.

- **Campos:** Nome (sigla, ex.: kg, lt, un) e Descrição.
- Somente unidades **ativas** aparecem no formulário de cotação do fornecedor.
- Adicione novas unidades conforme necessário — elas aparecem automaticamente no formulário público.
            """)

        with st.expander("📌 Usuários"):
            st.markdown("""
Gerenciamento de quem acessa o sistema.

- **Perfis disponíveis:** Digitador, Comprador, Administrador.
- Para cada usuário é possível definir permissões individuais — o que pode ou não acessar — independentemente do perfil base.
- Novos usuários recebem uma senha temporária e são obrigados a trocá-la no primeiro acesso.
- Usuários inativos não conseguem fazer login.
- **Unidades de acesso:** define a quais unidades hoteleiras o usuário tem acesso (para digitadores, por exemplo).
            """)

        with st.expander("📌 Orçamentos"):
            st.markdown("""
Define o valor de orçamento mensal por unidade hoteleira.

- Informado em reais (R$) por unidade e por mês/ano.
- Utilizado no relatório **Orçamento vs. Gasto** para mostrar se as compras estão dentro do previsto.
            """)

        with st.expander("📌 Backup / Exportar"):
            st.markdown("""
Permite exportar os dados do sistema em formato de planilha para backup externo ou análise.

- Exporte qualquer tabela do sistema para ter uma cópia dos dados.
- Recomenda-se realizar backups periódicos, especialmente antes de alterações em massa.
            """)


# ══════════════════════════════════════════════════════════════════════════════
# MINHA CONTA
# ══════════════════════════════════════════════════════════════════════════════
with ti["🔑 Minha Conta"]:
    st.subheader("Minha Conta")
    st.markdown("Configurações relacionadas à sua própria conta de acesso.")

    with st.expander("📌 Como alterar a sua senha"):
        st.markdown("""
1. Acesse **Minha Senha** no menu lateral.
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
- Caso suspeite que sua senha foi comprometida, troque-a imediatamente em **Minha Senha**.
        """)
