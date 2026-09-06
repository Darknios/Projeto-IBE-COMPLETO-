# Frequência IBE

Aplicativo Streamlit para consultar e lançar as contagens dos cultos de domingo da Igreja Batista Emanuel. O dashboard é público; a tela de lançamento tem acesso temporário restrito à recepção e foi pensada para uso no celular.

Link do projeto: https://recepcao-ibe.streamlit.app/

## Primeiro uso no Supabase

1. No **SQL Editor** do Supabase, execute [`supabase/001_ibe_contagens.sql`](supabase/001_ibe_contagens.sql).
2. Em **Project Settings → API**, copie a URL do projeto, a chave `anon` e a chave `service_role`.
3. Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` e preencha os valores reais. Esse arquivo é ignorado pelo Git.

> A chave `service_role` só pode existir nos Secrets do Streamlit. Nunca a use em páginas web, no navegador ou no repositório.

## Executar localmente

```powershell
pip install -r requirements.txt
streamlit run IBE.py
```

No Streamlit Cloud, cadastre os mesmos valores de `.streamlit/secrets.toml.example` em **App settings → Secrets**.

## Acesso temporário ao lançamento

O modelo de Secrets configura inicialmente:

```toml
ENTRY_USERNAME = "ibe"
ENTRY_PASSWORD = "ibe"
```

Troque a senha antes de publicar. Essa é uma proteção temporária de interface; quando houver necessidade de contas individuais, o próximo passo será migrar para Supabase Auth.

## Importar o histórico da planilha

Depois de executar o SQL e instalar as dependências, primeiro valide a planilha:

```powershell
python scripts/import_historico.py --file "Formulário de contagem Recepção (IBE) (respostas).xlsx" --dry-run
```

Para enviar os dados, defina as variáveis somente na sessão atual do PowerShell e execute a importação:

```powershell
$env:SUPABASE_URL = "https://seu-projeto.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "sua-chave-service-role"
python scripts/import_historico.py --file "Formulário de contagem Recepção (IBE) (respostas).xlsx"
Remove-Item Env:SUPABASE_URL, Env:SUPABASE_SERVICE_ROLE_KEY
```

O importador usa a combinação de data, grupo e horário para atualizar registros já enviados em vez de duplicá-los.
