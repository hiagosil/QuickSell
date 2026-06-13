# QuickSell v2

Gerador de lojas virtuais com painel de gestão completo.

## Novidades v2

| Feature | Detalhes |
|---------|----------|
| **Upload de imagens** | Drag & drop, JPG/PNG/WEBP, máx 5 MB, preview em tempo real |
| **Categorias** | CRUD completo, slug automático, filtro na loja pública |
| **Estoque** | `stock_quantity`, `sku`, barra visual, ajuste inline, bloqueio sem estoque |
| **Dashboard** | Sidebar com navegação, stats cards, filtro por categoria/status |

## Instalação

```bash
pip install -r requirements.txt
python app.py
```

## Migração (banco existente)

Se já existia um banco de dados da v1:

```bash
python migrate_v2.py
```

## Estrutura

```
quicksell/
├── app/
│   ├── models/
│   │   ├── category.py     ← NOVO
│   │   ├── product.py      ← atualizado (sku, stock_quantity, image_path, category_id)
│   │   └── store.py        ← atualizado (categories relationship)
│   ├── routes/
│   │   ├── category.py     ← NOVO (CRUD categorias)
│   │   └── product.py      ← atualizado (upload, estoque inline, SKU)
│   ├── utils/
│   │   └── upload.py       ← NOVO (save/delete imagens)
│   ├── templates/
│   │   └── dashboard/
│   │       ├── categories.html  ← NOVO
│   │       ├── products.html    ← atualizado
│   │       └── edit_product.html← atualizado
│   ├── static/uploads/     ← pasta de imagens (criada automaticamente)
│   └── config.py           ← atualizado (UPLOAD_FOLDER, MAX_CONTENT_LENGTH)
└── migrate_v2.py           ← NOVO
```

## Rotas novas

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/stores/<id>/categories` | Listar categorias |
| POST | `/stores/<id>/categories/new` | Criar categoria |
| POST | `/stores/<id>/categories/<id>/edit` | Editar categoria |
| POST | `/stores/<id>/categories/<id>/delete` | Excluir categoria |
| POST | `/stores/<id>/products/<id>/stock` | Ajuste rápido de estoque |

## Regras de estoque

- Produto com `effective_stock == 0` fica com botão "Esgotado" desabilitado na loja pública
- Estoque ≤ 5 exibe badge "Baixo" em laranja
- Ajuste de estoque disponível inline na tabela de produtos (sem recarregar página)
- `Product.decrement_stock(qty)` é chamado automaticamente ao confirmar pedido

## Upload de imagens

- Aceita: `.jpg`, `.jpeg`, `.png`, `.webp`
- Limite: 5 MB por arquivo
- Salvo em: `app/static/uploads/<uuid>.<ext>`
- Campo `image_path` salvo no banco (relativo à pasta uploads)
- Propriedade `product.image` resolve a imagem correta (upload local > URL externa)
