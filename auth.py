"""Login do painel IBE usando Supabase Auth.

A autenticação usa a chave publishable/anon (pública) e a autorização usa
somente app_metadata emitido pelo Supabase para o usuário autenticado.
"""
from __future__ import annotations

import hmac
import re
import unicodedata
from collections.abc import Mapping
from typing import Any

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from supabase import create_client

DEFAULT_ALLOWED_CHURCH_ID = "34a358e0-eeb5-4975-83ca-a19f06ce687d"
DEFAULT_ALLOWED_ROLES = ("EQUIPE", "GERENTE", "ANALISTA", "LIDER", "CO-LIDER", "ADMIN")
DEFAULT_SUPABASE_URL = "https://fyyvubvceijyeuhvncri.supabase.co"
DEFAULT_SUPABASE_ANON_KEY = "sb_publishable_AvqTQvdX630cTqbJ0kIlHQ_Ky-BaS8i"


class AuthenticationError(RuntimeError):
    pass


class AuthorizationError(RuntimeError):
    pass


def _secret(secrets: Mapping[str, Any], key: str, default: Any = None) -> Any:
    try:
        value = secrets.get(key)
    except StreamlitSecretNotFoundError:
        value = None
    return default if value in (None, "") else value


def _canonical(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _lookup(mapping: Mapping[str, Any] | None, *names: str) -> Any:
    if not mapping:
        return None
    normalized = {_canonical(key): value for key, value in mapping.items()}
    for name in names:
        key = _canonical(name)
        if key in normalized and normalized[key] not in (None, ""):
            return normalized[key]
    return None


def _normalize_role(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    role = text.strip().upper().replace("_", "-").replace(" ", "-")
    role = re.sub(r"-+", "-", role)
    if role == "COLIDER":
        role = "CO-LIDER"
    return role


def _allowed_church_id(secrets: Mapping[str, Any]) -> str:
    return str(_secret(secrets, "ALLOWED_CHURCH_ID", DEFAULT_ALLOWED_CHURCH_ID)).strip()


def _allowed_roles(secrets: Mapping[str, Any]) -> tuple[str, ...]:
    configured = _secret(secrets, "AUTH_ALLOWED_ROLES")
    if configured:
        values = [part.strip() for part in str(configured).split(",") if part.strip()]
        if values:
            return tuple(_normalize_role(value) for value in values)
    return DEFAULT_ALLOWED_ROLES


def _anon_client(secrets: Mapping[str, Any]):
    url = str(_secret(secrets, "SUPABASE_URL", DEFAULT_SUPABASE_URL)).strip()
    key = str(_secret(secrets, "SUPABASE_ANON_KEY", DEFAULT_SUPABASE_ANON_KEY)).strip()
    if not url or not key:
        raise AuthenticationError("Configuração de autenticação indisponível.")
    return create_client(url, key)


def _user_value(user: object, key: str, default: Any = None) -> Any:
    if isinstance(user, Mapping):
        return user.get(key, default)
    value = getattr(user, key, default)
    if value is not None:
        return value
    # Compatibilidade com modelos pydantic usados pelo supabase-py.
    try:
        dumped = user.model_dump()
    except Exception:
        dumped = None
    if isinstance(dumped, Mapping):
        return dumped.get(key, default)
    return default


def _metadata(user: object) -> Mapping[str, Any]:
    value = _user_value(user, "app_metadata", {})
    return value if isinstance(value, Mapping) else {}


def _friendly_auth_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "email not confirmed" in message or "email_not_confirmed" in message:
        return "Esta conta ainda não foi confirmada no Supabase Auth."
    if "invalid login credentials" in message or "invalid_credentials" in message:
        return "Usuário ou senha incorretos."
    if "rate limit" in message or "too many" in message:
        return "Muitas tentativas seguidas. Aguarde um pouco e tente novamente."
    return "Usuário ou senha incorretos."


def authenticate(
    secrets: Mapping[str, Any],
    *,
    church_id_input: str,
    login: str,
    password: str,
) -> dict[str, Any]:
    email = str(login or "").strip().lower()
    password = str(password or "").strip()
    if not email or not password:
        raise AuthenticationError("Informe usuário e senha.")
    if "@" not in email:
        raise AuthenticationError("Use o e-mail de acesso cadastrado no Supabase.")

    client = _anon_client(secrets)
    try:
        response = client.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:
        raise AuthenticationError(_friendly_auth_error(exc)) from exc

    user = getattr(response, "user", None)
    session = getattr(response, "session", None)
    if user is None or session is None:
        raise AuthenticationError("Não foi possível iniciar a sessão.")

    app_metadata = _metadata(user)
    role = _normalize_role(_lookup(app_metadata, "perfil", "role", "cargo"))
    name = _lookup(app_metadata, "nome", "name", "display_name")

    if role not in _allowed_roles(secrets):
        try:
            client.auth.sign_out()
        except Exception:
            pass
        raise AuthorizationError("Seu perfil não possui acesso a este painel.")

    user_id = str(_user_value(user, "id", "") or "").strip()
    user_email = str(_user_value(user, "email", email) or email).strip().lower()
    return {
        "user_id": user_id,
        "email": user_email,
        "name": str(name or user_email),
        "role": role,
        "church_id": _allowed_church_id(secrets),
        "access_token": str(getattr(session, "access_token", "") or ""),
        "refresh_token": str(getattr(session, "refresh_token", "") or ""),
    }


def initialize_auth_state() -> None:
    st.session_state.setdefault("dashboard_authenticated", False)
    st.session_state.setdefault("dashboard_user", None)
    st.session_state.setdefault("login_error", None)


def current_user() -> dict[str, Any] | None:
    user = st.session_state.get("dashboard_user")
    return user if isinstance(user, dict) else None


def logout() -> None:
    st.session_state.dashboard_authenticated = False
    st.session_state.dashboard_user = None
    st.session_state.login_error = None


def _inject_login_css() -> None:
    """Estilo isolado da tela de login.

    Mantemos todos os seletores sob ``.st-key-login_card`` para não contaminar
    o dashboard depois da autenticação.
    """
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 50% -8%, rgba(35,87,175,.62) 0%, rgba(18,47,104,.44) 25%, rgba(8,24,55,.92) 58%, #050b18 100%) !important;
        }
        [data-testid="stHeader"] { background: transparent !important; }
        [data-testid="stSidebar"] { display: none !important; }

        /* O cartão usa a largura da página; não fica preso em uma coluna estreita. */
        .block-container {
            width: 100% !important;
            max-width: 980px !important;
            padding: 1rem 1rem 2rem !important;
        }
        .login-brand-copy {
            text-align: center;
            margin: .1rem auto .25rem;
            font-family: "Segoe UI", Arial, sans-serif;
        }
        .login-brand-kicker {
            color: #70adff;
            font-size: .72rem;
            font-weight: 800;
            letter-spacing: .22em;
        }
        .login-brand-title {
            color: #f8fafc;
            font-size: .92rem;
            font-weight: 600;
            margin-top: .2rem;
        }

        .st-key-login_card {
            width: min(100%, 520px) !important;
            max-width: 520px !important;
            margin: .7rem auto 0 !important;
            padding: 1.5rem 1.6rem 1.45rem !important;
            box-sizing: border-box !important;
            border-radius: 24px !important;
            border: 1px solid rgba(126,162,220,.27) !important;
            background: linear-gradient(180deg, rgba(16,37,78,.98), rgba(7,20,45,.985)) !important;
            box-shadow: 0 28px 70px rgba(0,0,0,.40), inset 0 1px 0 rgba(255,255,255,.04) !important;
            font-family: "Segoe UI", Arial, sans-serif !important;
        }
        .st-key-login_card * { box-sizing: border-box; }
        .st-key-login_card div[data-testid="stImage"] {
            width: 100% !important;
            display: flex;
            align-items: center;
            justify-content: center;
            align-self: center;
            text-align: center;
            margin: 0 auto .3rem;
        }
        .st-key-login_card div[data-testid="stImage"] img {
            display: block !important;
            margin: 0 auto !important;
            width: auto !important;
            max-width: 210px !important;
            max-height: 92px !important;
            object-fit: contain !important;
            background: transparent !important;
        }
        .login-title {
            color: #fff;
            text-align: center;
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.1;
            margin-top: .1rem;
        }
        .login-subtitle {
            color: #a9b7cf;
            text-align: center;
            margin: .38rem 0 1.15rem;
            font-size: .93rem;
        }

        /* Inputs: mesma aparência em foco, preenchido e senha com ícone de olho. */
        .st-key-login_card [data-testid="stTextInput"] { margin-bottom: .08rem; }
        .st-key-login_card [data-testid="stTextInput"] label,
        .st-key-login_card [data-testid="stTextInput"] label p {
            color: #f5f7fb !important;
            font-size: .84rem !important;
            line-height: 1.2 !important;
            font-weight: 700 !important;
            font-family: "Segoe UI", Arial, sans-serif !important;
        }
        .st-key-login_card div[data-baseweb="input"],
        .st-key-login_card div[data-baseweb="base-input"] {
            width: 100% !important;
            min-height: 46px !important;
            background: #0a1730 !important;
            border: 1px solid #35547c !important;
            border-radius: 10px !important;
            box-shadow: inset 0 0 0 1px rgba(255,255,255,.025) !important;
            overflow: hidden !important;
        }
        .st-key-login_card div[data-baseweb="input"]:focus-within {
            border-color: #4d9cff !important;
            box-shadow: 0 0 0 2px rgba(77,156,255,.18) !important;
        }
        .st-key-login_card div[data-baseweb="input"] input,
        .st-key-login_card div[data-baseweb="base-input"] input {
            min-height: 44px !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            caret-color: #ffffff !important;
            background: #0a1730 !important;
            font-size: 16px !important;
            font-family: "Segoe UI", Arial, sans-serif !important;
        }
        .st-key-login_card div[data-baseweb="input"] input::placeholder {
            color: #8fa2bf !important;
            -webkit-text-fill-color: #8fa2bf !important;
            opacity: 1 !important;
        }
        .st-key-login_card div[data-baseweb="input"] button,
        .st-key-login_card div[data-baseweb="input"] button * {
            color: #ffffff !important;
            fill: #ffffff !important;
            background: transparent !important;
        }
        /* Senha: elimina a segunda borda/caixa que aparecia ao redor do botão do olho. */
        .st-key-auth_password div[data-baseweb="input"] {
            position: relative !important;
            padding-right: 0 !important;
            overflow: hidden !important;
        }
        .st-key-auth_password div[data-baseweb="input"] input {
            padding-right: 3.2rem !important;
        }
        .st-key-auth_password div[data-baseweb="input"] button {
            position: absolute !important;
            right: 0 !important;
            top: 0 !important;
            bottom: 0 !important;
            width: 3rem !important;
            min-width: 3rem !important;
            height: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            border: 0 !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            background: #0a1730 !important;
        }
        .st-key-auth_password div[data-baseweb="input"] button:focus,
        .st-key-auth_password div[data-baseweb="input"] button:hover {
            border: 0 !important;
            box-shadow: none !important;
            background: #0a1730 !important;
        }
        /* Remove o balão “Press Enter to submit form” do Streamlit. */
        .st-key-login_card [data-testid="InputInstructions"],
        .st-key-login_card [data-testid="stTextInput"] small {
            display: none !important;
        }

        /* Checkbox real e clicável. */
        .st-key-auth_remember { margin: .15rem 0 .72rem !important; }
        .st-key-auth_remember [data-testid="stCheckbox"] label {
            display: inline-flex !important;
            align-items: center !important;
            gap: .38rem !important;
            color: #c7d2e4 !important;
            font-family: "Segoe UI", Arial, sans-serif !important;
        }
        .st-key-auth_remember [data-testid="stCheckbox"] label p {
            color: #c7d2e4 !important;
            font-size: .83rem !important;
            font-weight: 500 !important;
            margin: 0 !important;
        }
        .st-key-auth_remember [data-testid="stCheckbox"] span[data-baseweb="checkbox"] > div {
            width: 18px !important;
            height: 18px !important;
            border-radius: 4px !important;
        }

        .login-security {
            margin: .1rem 0 .78rem;
            padding: .72rem .78rem;
            text-align: center;
            color: #b8c7dd;
            font-size: .76rem;
            line-height: 1.45;
            border: 1px solid rgba(96,165,250,.19);
            border-radius: 10px;
            background: rgba(30,64,175,.10);
        }
        .st-key-dashboard_login_button button {
            width: 100% !important;
            min-height: 3rem !important;
            border: none !important;
            border-radius: 10px !important;
            color: #fff !important;
            font-size: .96rem !important;
            font-weight: 700 !important;
            font-family: "Segoe UI", Arial, sans-serif !important;
            background: linear-gradient(135deg,#2d8cff,#1465ee) !important;
            box-shadow: 0 10px 28px rgba(20,121,255,.25) !important;
        }
        .st-key-dashboard_login_button button:hover {
            filter: brightness(1.06);
            border: none !important;
        }
        .st-key-login_card [data-testid="stAlert"] {
            margin-top: .65rem;
            font-family: "Segoe UI", Arial, sans-serif !important;
        }
        .login-footer {
            text-align: center;
            color: #7285a5;
            font-size: .67rem;
            font-weight: 700;
            letter-spacing: .12em;
            margin: 1rem 0 0;
            font-family: "Segoe UI", Arial, sans-serif;
        }

        @media (max-width: 600px) {
            .block-container { padding: .55rem .7rem 1.5rem !important; }
            .login-brand-copy { margin-top: 0; }
            .st-key-login_card {
                width: 100% !important;
                margin-top: .4rem !important;
                padding: 1.15rem 1rem 1.05rem !important;
                border-radius: 19px !important;
            }
            .st-key-login_card div[data-testid="stImage"] img {
                max-width: 190px !important;
                max-height: 82px !important;
            }
            .login-title { font-size: 1.72rem; }
            .login-subtitle { margin-bottom: .95rem; }
            .login-footer { font-size: .58rem; letter-spacing: .08em; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def require_dashboard_login(secrets: Mapping[str, Any]) -> bool:
    initialize_auth_state()
    if st.session_state.dashboard_authenticated and current_user():
        return True

    _inject_login_css()
    st.markdown(
        """
        <div class="login-brand-copy">
            <div class="login-brand-kicker">PAINEL IBE</div>
            <div class="login-brand-title">Frequência &amp; gestão</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Não usamos st.columns aqui. Em telas estreitas as colunas continuavam lado
    # a lado e esmagavam o cartão, exatamente como no print reportado.
    with st.container(key="login_card"):
        st.image("logo.png", width=200)
        st.markdown(
            """
            <div class="login-title">Acessar Painel</div>
            <div class="login-subtitle">Entre com seu usuário e senha</div>
            """,
            unsafe_allow_html=True,
        )

        with st.form(key="login_form"):
            login_value = st.text_input(
                "Usuário",
                placeholder="Seu usuário ou e-mail",
                autocomplete="username",
                key="auth_login",
            )
            password_value = st.text_input(
                "Senha",
                type="password",
                placeholder="Sua senha",
                autocomplete="current-password",
                key="auth_password",
            )
            remember_session = st.checkbox(
                "Lembrar nesta sessão",
                value=True,
                key="auth_remember",
            )
            submitted = st.form_submit_button(
                "Entrar",
                type="primary",
                use_container_width=True,
                key="dashboard_login_button",
            )

        if submitted:
            st.session_state.login_error = None
            login_value = str(st.session_state.get("auth_login") or "").strip()
            password_value = str(st.session_state.get("auth_password") or "").strip()
            try:
                user = authenticate(
                    secrets,
                    church_id_input="",
                    login=login_value,
                    password=password_value,
                )
            except (AuthenticationError, AuthorizationError) as error:
                st.session_state.login_error = str(error)
            except Exception:
                st.session_state.login_error = "Não foi possível validar o acesso agora. Tente novamente."
            else:
                user["remember_session"] = bool(remember_session)
                st.session_state.dashboard_user = user
                st.session_state.dashboard_authenticated = True
                st.session_state.login_error = None
                st.rerun()

        if st.session_state.login_error:
            st.error(st.session_state.login_error)

    st.markdown(
        "<div class='login-footer'>ACESSO PROTEGIDO</div>",
        unsafe_allow_html=True,
    )
    return False
