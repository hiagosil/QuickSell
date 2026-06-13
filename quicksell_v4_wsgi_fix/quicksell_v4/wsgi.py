"""
QuickSell - Ponto de entrada WSGI

Produção (Render): gunicorn aponta para este módulo via Procfile:
    web: gunicorn wsgi:app

IMPORTANTE — por que este arquivo se chama "wsgi.py" e não "app.py":
    O projeto tem um PACOTE chamado app/ (app/__init__.py com create_app()).
    Se este arquivo de entrada também se chamasse "app.py", haveria uma
    colisão de nomes: em Python, ao fazer `import app`, o pacote app/
    (diretório com __init__.py) tem prioridade sobre o módulo app.py.
    Resultado: gunicorn executa `from app import app`, mas "app" resolve
    para o PACOTE (que expõe create_app, db, etc., não um objeto Flask
    chamado "app") → AttributeError: module 'app' has no attribute 'app'.

    Renomear para wsgi.py elimina a ambiguidade — "wsgi" não colide com
    nenhum nome usado no projeto.

Local: python wsgi.py — roda o servidor de desenvolvimento do Flask.
"""

from app import create_app

# Objeto WSGI usado pelo gunicorn em produção.
# create_app() sem argumento lê FLASK_ENV/ENV automaticamente —
# em Render, defina FLASK_ENV=production.
app = create_app()

if __name__ == "__main__":
    # Execução local direta — força development para garantir reload/debug
    # mesmo que FLASK_ENV não esteja definido no shell do desenvolvedor.
    dev_app = create_app("development")
    dev_app.run(debug=True, host="0.0.0.0", port=5000)
