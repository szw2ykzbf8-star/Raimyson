# H Hotéis — Sistema de Compras

Sistema de gestão de compras para múltiplas unidades hoteleiras.

## Instalação

```bash
pip install -r requirements.txt
```

## Configuração

1. Copie `credentials.json.example` para `credentials.json`
2. Preencha com as credenciais da sua conta de serviço Google
3. Habilite as APIs no Google Cloud Console:
   - Google Sheets API
   - Google Drive API

## Executar

```bash
streamlit run app.py
```

## Usuário padrão (primeiro acesso)

- **Login:** admin
- **Senha:** admin123

> Altere a senha após o primeiro acesso em Configurações → Usuários.

## Conta de serviço Google

Compartilhe sua planilha com o e-mail da conta de serviço:
`compras-h-hoteis@h-hoteis-compras.iam.gserviceaccount.com`
