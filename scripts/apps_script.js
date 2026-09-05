/**
 * apps_script.js — Middleware Google Apps Script para o PWA mobile FinTrack
 *
 * COMO USAR:
 * 1. Abra a planilha FinTrack no Google Sheets
 * 2. Clique em Extensões → Apps Script
 * 3. Apague o conteúdo do editor e cole TODO o conteúdo deste arquivo
 * 4. Altere SECRET_KEY abaixo para uma senha forte (a mesma que colocar no index.html)
 * 5. Clique em Salvar (ícone de disquete)
 * 6. Clique em Implantar → Nova implantação
 *    - Tipo: Aplicativo da Web
 *    - Executar como: Eu (sua conta Google)
 *    - Quem tem acesso: Qualquer pessoa
 * 7. Clique em Implantar e copie a URL gerada
 * 8. Cole essa URL como APPS_SCRIPT_URL no mobile/index.html
 *
 * SEGURANÇA:
 * - Toda requisição POST deve incluir o campo "secret" igual a SECRET_KEY
 * - Requisições GET retornam apenas dados públicos (categorias, contas, cartões)
 *   sem autenticação (o dispositivo já tem autenticação nativa)
 * - Em produção, considere adicionar autenticação também ao GET
 */

const SECRET_KEY = "TROQUE_ESTA_CHAVE_POR_UMA_SENHA_FORTE";

// ─── Roteador principal ───────────────────────────────────────────────────────

function doGet(e) {
  try {
    const action = (e.parameter && e.parameter.action) || "status";
    let result;

    switch (action) {
      case "status":
        result = { ok: true, msg: "FinTrack API ativa" };
        break;
      case "categorias":
        result = getCategorias();
        break;
      case "contas":
        result = getContas();
        break;
      case "cartoes":
        result = getCartoes();
        break;
      default:
        result = { ok: false, error: "Ação desconhecida" };
    }

    return jsonResponse(result);
  } catch (err) {
    return jsonResponse({ ok: false, error: err.message });
  }
}

function doPost(e) {
  try {
    let payload;
    try {
      payload = JSON.parse(e.postData.contents);
    } catch (_) {
      return jsonResponse({ ok: false, error: "JSON inválido" });
    }

    // Verificação do secret
    if (!payload.secret || payload.secret !== SECRET_KEY) {
      return jsonResponse({ ok: false, error: "Não autorizado" });
    }

    const action = payload.action || "";
    let result;

    switch (action) {
      case "salvar_gasto":
        result = salvarGasto(payload);
        break;
      default:
        result = { ok: false, error: "Ação desconhecida: " + action };
    }

    return jsonResponse(result);
  } catch (err) {
    return jsonResponse({ ok: false, error: err.message });
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function jsonResponse(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}

function getSheet(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ws = ss.getSheetByName(name);
  if (!ws) throw new Error("Aba não encontrada: " + name);
  return ws;
}

function generateId() {
  return Utilities.getUuid();
}

function nowIso() {
  return new Date().toISOString().replace("T", " ").substring(0, 19);
}

/**
 * Lê uma aba como array de objetos, usando a primeira linha como cabeçalhos.
 */
function sheetToObjects(ws) {
  const data = ws.getDataRange().getValues();
  if (data.length < 2) return [];
  const headers = data[0];
  return data.slice(1).map(row => {
    const obj = {};
    headers.forEach((h, i) => { obj[h] = String(row[i]); });
    return obj;
  });
}

// ─── Leitura de dados (GET) ───────────────────────────────────────────────────

function getCategorias() {
  const rows = sheetToObjects(getSheet("categorias"));
  const ativas = rows
    .filter(r => r.ativo === "True")
    .map(r => ({ id: r.id, nome: r.nome, icone: r.icone }));
  return { ok: true, data: ativas };
}

function getContas() {
  const rows = sheetToObjects(getSheet("contas_bancarias"));
  const ativas = rows
    .filter(r => r.ativo === "True")
    .map(r => ({ id: r.id, nome: r.nome, tipo: r.tipo }));
  return { ok: true, data: ativas };
}

function getCartoes() {
  const rows = sheetToObjects(getSheet("cartoes"));
  const ativos = rows
    .filter(r => r.ativo === "True")
    .map(r => ({
      id: r.id,
      nome: r.nome,
      dia_fechamento: r.dia_fechamento,
      dia_vencimento: r.dia_vencimento,
    }));
  return { ok: true, data: ativos };
}

// ─── Escrita de dados (POST) ──────────────────────────────────────────────────

/**
 * Salva um gasto recebido do PWA mobile.
 *
 * Campos esperados no payload:
 *   data_compra    : "YYYY-MM-DD"
 *   valor_total    : número
 *   num_parcelas   : inteiro (1 para à vista)
 *   categoria      : string (nome da categoria)
 *   forma_pagamento: "Dinheiro" | "Pix" | "Débito" | "Crédito"
 *   conta_cartao   : string (nome da conta ou cartão)
 *   descricao      : string (opcional)
 *
 * Para compras parceladas (forma_pagamento === "Crédito" && num_parcelas > 1),
 * o script cria uma linha por parcela com mes_referencia calculado a partir
 * do cartão (dia_fechamento e dia_vencimento lidos da aba cartoes).
 */
function salvarGasto(payload) {
  // Validações básicas
  const required = ["data_compra", "valor_total", "num_parcelas",
                    "categoria", "forma_pagamento", "conta_cartao"];
  for (const field of required) {
    if (payload[field] === undefined || payload[field] === "") {
      return { ok: false, error: "Campo obrigatório ausente: " + field };
    }
  }

  const dataCompra    = String(payload.data_compra);
  const valorTotal    = parseFloat(payload.valor_total);
  const numParcelas   = parseInt(payload.num_parcelas) || 1;
  const categoria     = String(payload.categoria);
  const formaPgto     = String(payload.forma_pagamento);
  const contaCartao   = String(payload.conta_cartao);
  const descricao     = String(payload.descricao || "");

  if (isNaN(valorTotal) || valorTotal <= 0) {
    return { ok: false, error: "Valor inválido" };
  }

  const valorParcela = valorTotal / numParcelas;
  const idGrupo      = generateId();
  const ws           = getSheet("gastos");

  // Determina data de fatura e mes_referencia para cada parcela
  let parcelas;
  if (formaPgto === "Crédito") {
    parcelas = calcularParcelas(dataCompra, valorTotal, numParcelas, contaCartao);
  } else {
    // À vista: data_fatura = data_compra, mes_referencia = YYYY-MM da compra
    const mesRef = dataCompra.substring(0, 7);
    parcelas = [{
      data_fatura:    dataCompra,
      mes_referencia: mesRef,
      parcela_num:    1,
      total_parcelas: 1,
      valor_parcela:  valorTotal,
    }];
  }

  const rows = parcelas.map(p => [
    generateId(),         // id
    idGrupo,              // id_grupo
    dataCompra,           // data_compra
    p.data_fatura,        // data_fatura
    p.mes_referencia,     // mes_referencia
    String(p.parcela_num),
    String(p.total_parcelas),
    String(p.valor_parcela.toFixed(2)),
    String(valorTotal.toFixed(2)),
    categoria,
    formaPgto,
    contaCartao,
    descricao,
    nowIso(),             // criado_em
  ]);

  ws.getRange(ws.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);

  return {
    ok: true,
    msg: `${parcelas.length} parcela(s) salva(s)`,
    id_grupo: idGrupo,
  };
}

/**
 * Calcula as datas de fatura e mes_referencia para cada parcela de crédito.
 * Regra: ciclo começa no dia_fechamento. Compra feita no dia_fechamento ou
 * após → vai para o PRÓXIMO ciclo.
 */
function calcularParcelas(dataCompraStr, valorTotal, numParcelas, nomeCartao) {
  // Busca o cartão para pegar dia_fechamento e dia_vencimento
  let diaFechamento = 28; // fallback
  let diaVencimento = 10; // fallback

  try {
    const cartoes = sheetToObjects(getSheet("cartoes"));
    const cartao  = cartoes.find(c => c.nome === nomeCartao && c.ativo === "True");
    if (cartao) {
      diaFechamento = parseInt(cartao.dia_fechamento) || 28;
      diaVencimento = parseInt(cartao.dia_vencimento) || 10;
    }
  } catch (_) { /* usa fallback */ }

  const compra  = new Date(dataCompraStr + "T12:00:00");
  const diaCompra = compra.getDate();

  // Mês do primeiro ciclo: se diaCompra >= diaFechamento → próximo mês
  let anoCiclo  = compra.getFullYear();
  let mesCiclo  = compra.getMonth(); // 0-indexed

  if (diaCompra >= diaFechamento) {
    mesCiclo += 1;
    if (mesCiclo > 11) { mesCiclo = 0; anoCiclo += 1; }
  }

  const valorParcela = valorTotal / numParcelas;
  const parcelas = [];

  for (let i = 0; i < numParcelas; i++) {
    let anoFat = anoCiclo;
    let mesFat = mesCiclo + i;
    while (mesFat > 11) { mesFat -= 12; anoFat += 1; }

    // Dia de vencimento pode não existir no mês (ex: 31 em fevereiro)
    const ultimoDia = new Date(anoFat, mesFat + 1, 0).getDate();
    const diaVenc   = Math.min(diaVencimento, ultimoDia);
    const dataFatura = `${anoFat}-${String(mesFat + 1).padStart(2, "0")}-${String(diaVenc).padStart(2, "0")}`;
    const mesRef     = `${anoFat}-${String(mesFat + 1).padStart(2, "0")}`;

    parcelas.push({
      data_fatura:    dataFatura,
      mes_referencia: mesRef,
      parcela_num:    i + 1,
      total_parcelas: numParcelas,
      valor_parcela:  valorParcela,
    });
  }

  return parcelas;
}
