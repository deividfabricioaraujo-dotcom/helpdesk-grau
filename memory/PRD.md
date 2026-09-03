# PRD — grau TI (Sistema de Chamados / Helpdesk da grau Técnico)

## Problema original
Migrar o protótipo (Flask + CSV) para stack de produção (React + FastAPI + MongoDB) com:
formulário público de chamados (com identificação, sem senha), painel admin protegido para
2 técnicos (Deivid e Bruno), e assistente de IA "Deivid" (Gemini 3 Flash, somente leitura).
Tema escuro verde/preto, moderno e limpo (sem cara de IA / sem poluição visual).
Logo "grau TI" no topo do admin; "grau Técnico" na área pública.

## Arquitetura
- Frontend: React (CRA + craco), Tailwind, shadcn/ui, sonner, lucide-react. Alias `@/` = src.
  - Páginas: PublicPage (`/`), LoginPage (`/admin/login`), AdminPage (`/admin`, protegida).
  - AuthContext com token JWT em localStorage (`grau_token`), Authorization: Bearer.
- Backend: FastAPI, todas as rotas sob `/api`.
  - Auth: login por USERNAME, bcrypt hash, JWT (7 dias). Seed idempotente de 2 admins no startup.
  - Tickets: criar (público), listar/filtrar (admin), stats/KPIs, lookup público por código,
    mudar status (com auditoria), arquivar/desarquivar (flag `archived`, nunca deleta).
  - IA: POST /api/chat (StreamingResponse), Gemini 3 Flash via emergentintegrations +
    EMERGENT_LLM_KEY. Somente leitura; contexto = dados reais dos chamados (scope public/admin).
- DB: MongoDB. Coleções `admins`, `tickets`. Código do chamado = `GT-` + 6 hex.

## Personas
- Solicitante: abre chamado com nome + prédio/sala; acompanha por código; usa Deivid (público).
- Técnico/Admin (Deivid, Bruno): gerencia fila, muda status, arquiva, consulta Deivid (admin).

## Requisitos centrais (estáticos)
- Formulário público com identificação obrigatória (nome + prédio + sala).
- 2 logins separados com senha em hash; rotas admin protegidas.
- Arquivar (nunca deletar); auditoria de quem alterou o quê.
- IA somente leitura, Gemini 3 Flash.
- IDs únicos gerados pelo banco.

## Implementado (2026-06)
- [x] Auth JWT/bcrypt + seed dos 2 admins (deividsuporte2006, bruno).
- [x] Formulário público (identidade, andar/prédio/sala, status de 4 equipamentos OK/defeito,
      prioridade, flag Deivid, observações) + toasts.
- [x] Lookup público de status por código.
- [x] Painel admin: KPIs (abertos, em andamento, urgentes, resolvidos) com refresh ~15s,
      lista, busca, filtros (prédio/prioridade/status), status inline, arquivar/desarquivar,
      visão de arquivados, modal de histórico/auditoria.
- [x] Deivid IA (Gemini 3 Flash) com streaming, no público e no admin.
- [x] Tema verde/preto limpo; logos grau Técnico (público) e grau TI (admin).
- Testado: backend 19/19 pytest; frontend 13/13 fluxos E2E (testing agent, iteração 1).

## Backlog priorizado
- P1: Senhas mais fortes + troca de senha pelo próprio admin.
- P1: Notificação (e-mail/WhatsApp) quando chega chamado urgente.
- P2: Paginação e exportação de relatórios (CSV/PDF).
- P2: IA com escrita (criar/alterar via comando) com confirmação.
- P2: Rate limiting no /api/chat.
- P3: Substituir logo por arquivo enviado pelo usuário (aguardando upload).

## Próximas tarefas
- Aguardar o usuário enviar os arquivos de logo para aplicar as imagens reais.
- Coletar feedback após demonstração para a equipe de TI.
