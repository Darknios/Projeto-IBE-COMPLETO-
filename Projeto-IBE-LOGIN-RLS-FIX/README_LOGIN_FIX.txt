CORREÇÕES DESTA VERSÃO
- Login não interfere mais no CSS/layout do dashboard após autenticar.
- Dashboard original restaurado (gráficos, abas e filtros).
- Login usa Supabase Auth + app_metadata (igreja_id/perfil).
- Checkbox problemático removido; "Lembrar nesta sessão" é visual e usa a própria sessão do Streamlit.
- Fonte fixada em Segoe UI/Arial somente na tela de login.
- Mensagens de erro de login mais claras.

Usuário precisa ter em auth.users.raw_app_meta_data:
  igreja_id = 34a358e0-eeb5-4975-83ca-a19f06ce687d
  perfil = ADMIN (ou outro perfil permitido)

IMPORTANTE: não coloque service_role no Git/ZIP público. Configure nos Secrets do Streamlit Cloud.
