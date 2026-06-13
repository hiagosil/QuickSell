"""
QuickSell - Utils package

ARQUITETURA DE IMPORTS — regra fundamental:
  utils/ NÃO pode importar de models/ no nível de módulo.
  cart.py usa modelos, mas só é importado diretamente pelas rotas,
  nunca via este __init__.py, para evitar ciclo:
    models/__init__ → category → utils/__init__ → cart → models/__init__

Exportamos apenas utilitários sem dependência de models:
"""
from .helpers import slugify
from .upload  import save_product_image, delete_product_image, allowed_file

# cart NÃO é reexportado aqui.
# Importe diretamente: from app.utils.cart import add_to_cart, ...
